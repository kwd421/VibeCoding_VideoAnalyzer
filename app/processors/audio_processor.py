import numpy as np
import subprocess
import noisereduce as nr
import imageio_ffmpeg
from app.models.config_models import TranscriptSegment

class AudioProcessor:
    """[시니어 최적화] 오디오 추출 및 DSP 필터링 파이프라인 분리"""
    
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
            # stationary=True: 배경 소음이 일정한 경우(선풍기, 에어컨 등)에 최적화
            denoised = nr.reduce_noise(y=audio_data, sr=16000, stationary=True, prop_decrease=0.75)
            return denoised
        except Exception as e:
            print(f"Denoise Error: {e}")
            return audio_data

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
