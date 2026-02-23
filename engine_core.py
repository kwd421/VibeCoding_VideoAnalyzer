import os
import subprocess
import wave
import numpy as np
import threading
import torch
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps
import imageio_ffmpeg

class HyperTranscriptionEngine:
    def __init__(self):
        self.model_id = "large-v3-turbo"
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.fw_model = None
        self.vad_model = None
        self.cpu_cores = 8 

    def get_model(self):
        if self.fw_model is None:
            self.fw_model = WhisperModel(self.model_id, device="cpu", compute_type="int8", cpu_threads=self.cpu_cores, num_workers=2)
        return self.fw_model

    def get_vad_model(self):
        if self.vad_model is None:
            torch.set_num_threads(self.cpu_cores)
            self.vad_model = load_silero_vad()
        return self.vad_model

    def detect_speech_vad(self, audio_data, stop_event):
        """[시니어 최적화] 감도를 높인 고성능 VAD (누락 방지 로직 적용)"""
        model = self.get_vad_model()
        audio_tensor = torch.from_numpy(audio_data)
        
        # 감도 조절 파라미터 (더 민감하게 설정)
        # threshold: 낮을수록 작은 소리도 음성으로 인식 (0.35)
        # min_speech_duration_ms: 짧은 소리도 포함 (150ms)
        # speech_pad_ms: 음성 앞뒤로 여유를 주어 잘림 방지 (250ms)
        tss = get_speech_timestamps(
            audio_tensor, 
            model, 
            sampling_rate=16000,
            threshold=0.35,
            min_speech_duration_ms=150,
            min_silence_duration_ms=2000,
            speech_pad_ms=250
        )
        
        results = []
        for ts in tss:
            if stop_event.is_set(): break
            # 초 단위 변환
            results.append({'s': ts['start']/16000, 'e': ts['end']/16000, 't': "[VAD 감지 구간]"})
        return results

    def extract_audio(self, video_path, output_path):
        subprocess.run([
            self.ffmpeg_exe, '-y', '-i', video_path, 
            '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 
            output_path
        ], capture_output=True, check=True)

    def get_audio_info(self, audio_path):
        with wave.open(audio_path, 'rb') as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            duration = n_frames / 16000
        avg_rms = np.sqrt(np.mean(audio**2))
        return audio, avg_rms, duration

    def detect_peaks_only(self, audio, global_avg_rms, stop_event):
        """[시니어 최적화] 넘파이 벡터 연산을 이용한 초고속 피크 감지"""
        win_size = 1600
        n_chunks = len(audio) // win_size
        if n_chunks == 0: return []
        
        # 1. 윈도우별 RMS 계산 (벡터화)
        audio_chunks = audio[:n_chunks * win_size].reshape(n_chunks, win_size)
        all_rms = np.sqrt(np.mean(audio_chunks**2, axis=1))
        
        # 2. 로컬 평균 계산 (이동 평균)
        lookback = 10
        if len(all_rms) < lookback * 2: return []
        
        # 로컬 평균을 위한 슬라이딩 윈도우 합계
        local_avg = np.convolve(all_rms, np.ones(lookback*2)/ (lookback*2), mode='same')
        
        # 3. 조건 검사 (벡터화)
        # g_thresh: 전체 평균의 5배, local_thresh: 주변 평균의 3배, absolute: 최소 0.05 이상
        g_thresh = global_avg_rms * 5.0
        mask = (all_rms > g_thresh) & (all_rms > local_avg * 3.0) & (all_rms > 0.05)
        
        peak_indices = np.where(mask)[0]
        peaks = peak_indices * win_size / 16000
        
        # 4. 그룹화 로직 (유지)
        grouped = []
        if len(peaks) > 0:
            start_p = peaks[0]
            for j in range(1, len(peaks)):
                if stop_event.is_set(): break
                if peaks[j] - peaks[j-1] > 1.5:
                    grouped.append((start_p, peaks[j-1] + 0.1))
                    start_p = peaks[j]
            grouped.append((start_p, peaks[-1] + 0.1))
            
        return grouped

    def transcribe_stream_raw(self, audio_path, stop_event):
        model = self.get_model()
        segments, info = model.transcribe(
            audio_path, beam_size=1, language="ko", vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=1000)
        )
        total_dur = info.duration
        
        def safe_generator():
            last_text = ""
            repetition_count = 0
            for s in segments:
                if stop_event.is_set(): break
                if s.start >= total_dur: break
                text = s.text.strip()
                if len(text) > 300: continue
                if s.avg_logprob < -1.5: continue
                if text == last_text and len(text) > 5:
                    repetition_count += 1
                else:
                    repetition_count = 0
                if repetition_count >= 3: break 
                last_text = text
                yield s.start, min(s.end, total_dur), text
                
        return safe_generator(), total_dur
