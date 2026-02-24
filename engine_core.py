import os
import subprocess
import wave
import numpy as np
import threading
import torch
import gc
import glob
import tempfile
import shutil
from collections import Counter
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps
import imageio_ffmpeg

class HyperTranscriptionEngine:
    def __init__(self):
        self.model_id = "large-v3-turbo"
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.fw_model = None
        self.vad_model = None
        self.clip_model = None
        self.clip_processor = None
        self.cpu_cores = 4  

    def get_model(self):
        if self.fw_model is None:
            self.fw_model = WhisperModel(self.model_id, device="cpu", compute_type="int8", cpu_threads=self.cpu_cores, num_workers=2)
        return self.fw_model

    def get_vad_model(self):
        if self.vad_model is None:
            torch.set_num_threads(self.cpu_cores)
            self.vad_model = load_silero_vad()
        return self.vad_model

    def get_clip_model(self):
        """[시니어 최적화] CLIP 모델 Lazy Loading (필요할 때만 로드)"""
        if self.clip_model is None:
            model_name = "openai/clip-vit-base-patch32"
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.clip_model = CLIPModel.from_pretrained(model_name).to(device)
            self.clip_processor = CLIPProcessor.from_pretrained(model_name)
        return self.clip_model, self.clip_processor

    def load_audio_to_memory(self, video_path):
        cmd = [self.ffmpeg_exe, '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-f', 's16le', '-' ]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_audio, _ = process.communicate()
            audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
            duration = len(audio_np) / 16000.0
            del raw_audio
            return audio_np, duration
        except Exception as e: raise RuntimeError(f"메모리 로드 오류: {e}")

    def detect_speech_vad_stream(self, audio_data, stop_event, min_silence_ms=2000, speech_pad_ms=250):
        model = self.get_vad_model()
        sample_rate, chunk_size, overlap = 16000, 16000 * 60, 16000 * 2
        total_samples, processed_until = len(audio_data), 0
        for i in range(0, total_samples, chunk_size):
            if stop_event.is_set(): break
            start, end = i, min(i + chunk_size + overlap, total_samples)
            tss = get_speech_timestamps(torch.from_numpy(audio_data[start:end]), model, sampling_rate=sample_rate, threshold=0.35, min_speech_duration_ms=150, min_silence_duration_ms=min_silence_ms, speech_pad_ms=speech_pad_ms)
            offset, chunk_results = start / sample_rate, []
            for ts in tss:
                s_t, e_t = offset + ts['start']/sample_rate, offset + ts['end']/sample_rate
                if e_t <= processed_until: continue
                chunk_results.append({'s': s_t, 'e': e_t, 't': f"{e_t - s_t:.2f}s"})
            processed_until = (start + chunk_size) / sample_rate
            yield chunk_results, (min(start + chunk_size, total_samples) / total_samples) * 100

    def detect_peaks_stream(self, audio, stop_event):
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

    def detect_scenes_clip_stream(self, video_path, labels, stop_event, interval=10):
        """[시니어 최적화] CLIP 기반 제로샷 영상 분류 및 챕터 생성"""
        model, processor = self.get_clip_model()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tmp_dir = tempfile.mkdtemp()
        try:
            cmd = [self.ffmpeg_exe, '-y', '-i', video_path, '-vf', f'fps=1/{interval}', '-vsync', 'vfr', os.path.join(tmp_dir, 'frame_%04d.jpg')]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            frame_files = sorted(glob.glob(os.path.join(tmp_dir, "*.jpg")))
            total_frames, raw_preds = len(frame_files), []
            for i, img_path in enumerate(frame_files):
                if stop_event.is_set(): break
                inputs = processor(text=labels, images=Image.open(img_path), return_tensors="pt", padding=True).to(device)
                with torch.no_grad(): outputs = model(**inputs)
                raw_preds.append(outputs.logits_per_image.softmax(dim=1).argmax().item())
                yield [], ((i + 1) / total_frames) * 100
            if stop_event.is_set(): return
            window_size, smoothed = 5, []
            for i in range(len(raw_preds)):
                window = raw_preds[max(0, i-window_size//2) : min(len(raw_preds), i+window_size//2+1)]
                smoothed.append(Counter(window).most_common(1)[0][0])
            final_res, curr_label, start_t = [], smoothed[0] if smoothed else 0, 0
            for i, l_idx in enumerate(smoothed):
                if l_idx != curr_label:
                    final_res.append({'s': float(start_t), 'e': float(i * interval), 't': f"[{labels[curr_label]}]"})
                    start_t, curr_label = i * interval, l_idx
            if smoothed: final_res.append({'s': float(start_t), 'e': float(len(smoothed) * interval), 't': f"[{labels[curr_label]}]"})
            yield final_res, 100
        finally: shutil.rmtree(tmp_dir, ignore_errors=True)

    def transcribe_stream_raw(self, audio_data, stop_event):
        model = self.get_model()
        total_samples = len(audio_data)
        total_dur, chunk_size, search_samples = total_samples / 16000, 16000 * 600, 16000 * 10
        def safe_generator():
            start_idx = 0
            while start_idx < total_samples:
                if stop_event.is_set(): break
                base_end = start_idx + chunk_size
                if base_end >= total_samples: end_idx = total_samples
                else:
                    search_chunk = audio_data[max(start_idx, base_end - search_samples):base_end]
                    end_idx = max(start_idx, base_end - search_samples) + (np.argmin(np.sum(search_chunk[:(len(search_chunk)//1600)*1600].reshape(-1, 1600)**2, axis=1)) * 1600) if len(search_chunk) >= 1600 else base_end
                chunk, offset = audio_data[start_idx:end_idx], start_idx / 16000
                if len(chunk) > 16000:
                    segs, _ = model.transcribe(chunk, beam_size=1, language="ko", vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5), condition_on_previous_text=False, temperature=0.0)
                    for s in segs:
                        if stop_event.is_set(): break
                        yield {'s': offset + s.start, 'e': min(offset + s.end, total_dur), 't': s.text.strip()}
                gc.collect(); start_idx = end_idx
        return safe_generator(), total_dur
