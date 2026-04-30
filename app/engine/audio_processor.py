import numpy as np
import subprocess
import noisereduce as nr
import imageio_ffmpeg
import re
import gc
import torch
import torchaudio.functional as AF
from app.core.config_models import TranscriptSegment

try:
    from demucs.pretrained import get_model as demucs_get_model
    from demucs.apply import apply_model as demucs_apply_model
    HAS_DEMUCS = True
except ImportError:
    demucs_get_model = None
    demucs_apply_model = None
    HAS_DEMUCS = False

class AudioProcessor:
    """[시니어 최적화] 오디오 추출 및 DSP 필터링 파이프라인 분리"""
    _demucs_model = None
    _demucs_model_name = None
    _demucs_device = None
    
    @staticmethod
    def load_audio_to_memory(video_path, ffmpeg_exe=None):
        if ffmpeg_exe is None:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-f', 's16le', '-' ]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_audio, _ = process.communicate()
            audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
            duration = len(audio_np) / 16000.0
            del raw_audio
            import gc; gc.collect()
            return audio_np, duration
        except Exception as e: raise RuntimeError(f"메모리 로드 오류: {e}")

    @staticmethod
    def probe_audio_duration(video_path, ffmpeg_exe=None):
        if ffmpeg_exe is None:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, '-i', video_path]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            output = proc.stderr or ""
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
            if not match:
                raise RuntimeError("duration not found")
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except Exception as e:
            raise RuntimeError(f"길이 조회 오류: {e}")

    @staticmethod
    def iter_audio_chunks(video_path, ffmpeg_exe=None, chunk_duration_sec=600):
        if ffmpeg_exe is None:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        sample_rate = 16000
        bytes_per_sample = 2
        bytes_per_chunk = int(chunk_duration_sec * sample_rate * bytes_per_sample)
        cmd = [ffmpeg_exe, '-v', 'error', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', str(sample_rate), '-ac', '1', '-f', 's16le', '-']
        process = None
        chunk_index = 0
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while True:
                raw_audio = process.stdout.read(bytes_per_chunk)
                if not raw_audio:
                    break
                audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
                chunk_start_sec = chunk_index * chunk_duration_sec
                actual_duration = len(audio_np) / sample_rate
                yield audio_np, chunk_start_sec, actual_duration
                del raw_audio
                chunk_index += 1

            stderr_output = process.stderr.read().decode("utf-8", errors="ignore") if process.stderr else ""
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(stderr_output.strip() or f"ffmpeg exited with code {return_code}")
        except Exception as e:
            raise RuntimeError(f"청크 오디오 스트리밍 오류: {e}")
        finally:
            if process is not None:
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                if process.poll() is None:
                    process.kill()

    @staticmethod
    def detect_peaks_stream(audio, stop_event):
        win_size = 1600 
        n_chunks = len(audio) // win_size
        if n_chunks == 0: return
        all_rms = np.sqrt(np.mean(audio[:n_chunks * win_size].reshape(n_chunks, win_size)**2, axis=1))
        z_scores = (all_rms - np.mean(all_rms)) / (np.std(all_rms) + 1e-9)
        peaks = np.where(z_scores > 3.5)[0] * win_size / 16000
        for i in range(0, len(all_rms), 600):
            if stop_event.is_set(): break
            end_idx = min(i + 600, len(all_rms))
            curr_p = peaks[(peaks >= i * 0.1) & (peaks < end_idx * 0.1)]
            res = []
            if len(curr_p) > 0:
                s_p = curr_p[0]
                for j in range(1, len(curr_p)):
                    if curr_p[j] - curr_p[j-1] > 1.5: res.append({'s': s_p, 'e': curr_p[j-1] + 0.1, 't': "[볼륨 피크]"}); s_p = curr_p[j]
                res.append({'s': s_p, 'e': curr_p[-1] + 0.1, 't': "[볼륨 피크]"})
            yield res, (end_idx / len(all_rms)) * 100

    @staticmethod
    def denoise_audio(audio_data):
        """[시니어 최적화] noisereduce를 이용한 고성능 배경 소음 제거 (Stationary Noise Reduction)"""
        try:
            sample_count = len(audio_data)
            if sample_count < 512:
                return audio_data

            # 짧은 trailing chunk에서는 STFT 기본값이 과도해 예외가 날 수 있으므로
            # 입력 길이에 맞춰 FFT/overlap 파라미터를 보수적으로 축소한다.
            n_fft = min(1024, sample_count)
            if n_fft < 64:
                return audio_data

            win_length = n_fft
            hop_length = max(16, n_fft // 4)
            if hop_length >= n_fft:
                hop_length = max(8, n_fft // 2)

            denoised = nr.reduce_noise(
                y=np.asarray(audio_data, dtype=np.float32),
                sr=16000,
                stationary=True,
                prop_decrease=0.75,
                n_fft=n_fft,
                win_length=win_length,
                hop_length=hop_length,
            )
            return np.asarray(denoised, dtype=np.float32)
        except Exception as e:
            print(f"Denoise Error: {e}")
            return audio_data

    @classmethod
    def _get_demucs_model(cls, model_name="htdemucs"):
        if not HAS_DEMUCS:
            raise RuntimeError("demucs is not installed.")
        if cls._demucs_model is None or cls._demucs_model_name != model_name:
            cls._demucs_model = demucs_get_model(model_name)
            cls._demucs_model_name = model_name
        return cls._demucs_model

    @staticmethod
    def _get_demucs_device():
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    @classmethod
    def separate_vocals_demucs(cls, audio_data, sample_rate=16000, model_name="htdemucs"):
        """Experimental source separation using Demucs. Returns mono vocals at the original sample rate."""
        try:
            sample_count = len(audio_data)
            if sample_count < sample_rate:
                return audio_data

            model = cls._get_demucs_model(model_name)
            target_sr = int(getattr(model, "samplerate", 44100))
            target_ch = int(getattr(model, "audio_channels", 2))
            sources = list(getattr(model, "sources", []))
            if "vocals" not in sources:
                raise RuntimeError(f"Demucs model '{model_name}' does not expose vocals source: {sources}")
            vocals_idx = sources.index("vocals")
            device = cls._get_demucs_device()
            cls._demucs_device = device.type

            wav = torch.from_numpy(np.asarray(audio_data, dtype=np.float32)).unsqueeze(0)
            if sample_rate != target_sr:
                wav = AF.resample(wav, sample_rate, target_sr)
            if target_ch == 2:
                wav = wav.repeat(2, 1)
            elif target_ch != 1:
                wav = wav.repeat(target_ch, 1)
            wav = wav.unsqueeze(0)

            with torch.no_grad():
                separated = demucs_apply_model(
                    model,
                    wav,
                    device=device,
                    shifts=1,
                    split=True,
                    overlap=0.1,
                    progress=False,
                    num_workers=0,
                )

            vocals = separated[0, vocals_idx]
            if vocals.dim() == 2:
                vocals = vocals.mean(dim=0, keepdim=True)
            if target_sr != sample_rate:
                vocals = AF.resample(vocals, target_sr, sample_rate)
            vocals = vocals.squeeze(0).cpu().numpy().astype(np.float32, copy=False)
            return vocals
        except Exception as e:
            print(f"Demucs Error: {e}")
            return audio_data
        finally:
            gc.collect()

    @classmethod
    def release_cached_models(cls):
        try:
            cls._demucs_model = None
            cls._demucs_model_name = None
            cls._demucs_device = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass

    @staticmethod
    def filter_dominant_speaker(audio_data, segments):
        """[시니어 최적화] 에너지 기반 통계적 주인공 목소리 필터링 (RMS Thresholding)"""
        if not segments or len(segments) < 3: return segments
        
        energies = []
        for s in segments:
            seg_s = s.s if isinstance(s, TranscriptSegment) else s['s']
            seg_e = s.e if isinstance(s, TranscriptSegment) else s['e']
            start_i, end_i = int(seg_s * 16000), int(seg_e * 16000)
            chunk = audio_data[start_i:end_i]
            if len(chunk) > 0:
                energies.append(np.sqrt(np.mean(chunk**2)))
            else: energies.append(0)
            
        energies = np.array(energies)
        # 주인공 목소리 필터 임계값 완화 (0.8 -> 0.4) 및 안정성 강화
        threshold = np.mean(energies) * 0.4
        
        filtered = [seg for i, seg in enumerate(segments) if energies[i] >= threshold]
        return filtered
