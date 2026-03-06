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
import noisereduce as nr
import re
from collections import Counter
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps
import imageio_ffmpeg
import concurrent.futures
from config_models import AnalysisSettings, TranscriptSegment, TranscriptWord
from text_sanitizer import TextSanitizer
from audio_processor import AudioProcessor
from vision_processor import VisionProcessor

class HyperTranscriptionEngine:
    def __init__(self):
        self.model_id = "large-v3-turbo"
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.fw_model = None
        self.vad_model = None
        self.vision_processor = VisionProcessor(self._detect_best_device)
        self.clip_processor = None
        
        # [시니어 최적화] 하드웨어 코어의 50%만 동적으로 계산하여 할당 (100% 점유 방지)
        total_cores = os.cpu_count() or 4
        self.cpu_cores = max(1, int(total_cores * 0.5))
        self.device_info = "auto"
        
    def _detect_best_device(self, user_choice="auto"):
        """[시니어 하드웨어 분석] 환경에 맞는 텐서 연산 장치 동적 스캔"""
        if user_choice.startswith("cpu"):
            return "cpu"
        if user_choice != "auto":
            return user_choice
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _get_target_cores(self, device_mode="auto"):
        total_cores = os.cpu_count() or 4
        if "25" in device_mode: return max(1, int(total_cores * 0.25))
        if "50" in device_mode: return max(1, int(total_cores * 0.50))
        if "75" in device_mode: return max(1, int(total_cores * 0.75))
        return max(1, int(total_cores * 0.50)) # 기본값 50%

    def get_model(self, device_mode="auto"):
        target_threads = self._get_target_cores(device_mode)
        
        # 모델 리로드 조건: 디바이스가 바뀌었거나, CPU 모드인데 쓰레드 설정이 달라진 경우
        if self.fw_model is None or self.device_info != device_mode:
            self.device_info = device_mode
            best_device = self._detect_best_device(device_mode)
            # CTranslate2의 디바이스 맵핑 (cuda/cpu 외에는 fall back)
            ct2_dev = "cuda" if best_device == "cuda" else "cpu"
            c_type = "float16" if ct2_dev == "cuda" else "int8"
            
            # [시니어 최적화] Multi-worker 환경에서 Thread 뻥튀기를 방지하기 위해 Total Thread 제한
            workers = 2 if ct2_dev == "cpu" else 1
            threads_per_worker = max(1, target_threads // workers)
            
            self.fw_model = WhisperModel(self.model_id, device=ct2_dev, compute_type=c_type, cpu_threads=threads_per_worker, num_workers=workers)
        return self.fw_model

    def set_model_id(self, new_model_id):
        if self.model_id != new_model_id:
            self.model_id = new_model_id
            self.fw_model = None  # Force reload model

    def get_vad_model(self, device_mode="auto"):
        if self.vad_model is None:
            target_threads = self._get_target_cores(device_mode)
            torch.set_num_threads(target_threads)
            # Silero VAD 로드 패치 (Warning 방지)
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                self.vad_model = load_silero_vad()
            
            # 모델을 하드웨어 장치에 탑재
            best_dev = self._detect_best_device(device_mode)
            if best_dev != "cpu":
                self.vad_model = self.vad_model.to(best_dev)
                
        return self.vad_model

    def get_clip_model(self, device_mode="auto"):
        return self.vision_processor.get_clip_model(device_mode)

    def load_audio_to_memory(self, video_path):
        return AudioProcessor.load_audio_to_memory(video_path, self.ffmpeg_exe)

    def detect_speech_vad_stream(self, audio_data, stop_event, min_silence_ms=2000, speech_pad_ms=250, options=None):
        options = options or {}
        device_mode = options.get("device_mode", "auto")
        vad_threshold = options.get("vad_threshold", 0.35)
        model = self.get_vad_model(device_mode)
        sample_rate, chunk_size, overlap = 16000, 16000 * 60, 16000 * 2
        total_samples = len(audio_data)
        last_end_time = 0.0
        for i in range(0, total_samples, chunk_size):
            if stop_event.is_set(): break
            start, end = i, min(i + chunk_size + overlap, total_samples)
            tss = get_speech_timestamps(torch.from_numpy(audio_data[start:end]), model, sampling_rate=sample_rate, threshold=vad_threshold, min_speech_duration_ms=150, min_silence_duration_ms=min_silence_ms, speech_pad_ms=speech_pad_ms)
            offset, chunk_results = start / sample_rate, []
            for ts in tss:
                s_t, e_t = offset + ts['start']/sample_rate, offset + ts['end']/sample_rate
                if e_t <= last_end_time: continue # 완전히 이전 대사에 파묻힌 역전 현상 무시
                s_t = max(s_t, last_end_time) # 겹치는 시작점 보정
                if s_t >= e_t: continue
                chunk_results.append({'s': s_t, 'e': e_t, 't': f"{e_t - s_t:.2f}s"})
                last_end_time = max(last_end_time, e_t)
            yield chunk_results, (min(start + chunk_size, total_samples) / total_samples) * 100

    def detect_peaks_stream(self, audio, stop_event):
        return AudioProcessor.detect_peaks_stream(audio, stop_event)

    def detect_scenes_clip_stream(self, video_path, labels, stop_event, interval=10, options=None):
        return self.vision_processor.detect_scenes_clip_stream(video_path, labels, stop_event, self.ffmpeg_exe, interval, options)

    def denoise_audio(self, audio_data):
        return AudioProcessor.denoise_audio(audio_data)

    def filter_dominant_speaker(self, audio_data, segments):
        return AudioProcessor.filter_dominant_speaker(audio_data, segments)

    def transcribe_stream_raw(self, audio_data, stop_event, options: AnalysisSettings = None):
        if options is None: options = AnalysisSettings()
        device_mode = options.device_mode
        model = self.get_model(device_mode)
        
        beam_size = options.beam_size
        use_denoise = options.use_denoise
        use_dominant = options.use_dominant
        selected_lang = options.language
        if selected_lang == "auto": selected_lang = None
        vad_threshold = options.vad_threshold
        min_silence_ms = options.min_silence_ms
        speech_pad_ms = options.speech_pad_ms
        split_gap_sec = max(1.0, min_silence_ms / 1000.0)
        use_word_timestamps = options.use_word_timestamps
        use_whisper_vad = options.use_whisper_vad
        use_silero_vad = options.use_silero_vad

        # 소음 제거 적용
        if use_denoise:
            audio_data = self.denoise_audio(audio_data)

        total_samples = len(audio_data)
        # [CRITICAL] Stop 버튼 응답성을 1초 이내로 확보하기 위해 Whisper 청크 단위를 30초로 단축
        total_dur, chunk_size, search_samples = total_samples / 16000, 16000 * 30, 16000 * 5
        
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
                    # [시니어 최적화] VAD-Whisper 2-Tier Architecture 도입 여부
                    safe_tss = []
                    if use_silero_vad:
                        vad_model = self.get_vad_model(device_mode)
                        tss = get_speech_timestamps(torch.from_numpy(chunk), vad_model, sampling_rate=16000, threshold=vad_threshold, min_speech_duration_ms=150, min_silence_duration_ms=min_silence_ms, speech_pad_ms=speech_pad_ms)
                        
                        last_end_time = 0.0
                        for ts in tss:
                            vad_s = ts['start'] / 16000.0
                            vad_e = ts['end'] / 16000.0
                            if vad_e <= last_end_time: continue
                            vad_s = max(vad_s, last_end_time)
                            if vad_s >= vad_e: continue
                            safe_tss.append((vad_s, vad_e))
                            last_end_time = max(last_end_time, vad_e)
                    else:
                        safe_tss = [(0.0, len(chunk) / 16000.0)]
                        
                    def _process_ts(bounds):
                        vad_s, vad_e = bounds
                        if stop_event.is_set(): return []
                        sub_chunk = chunk[int(vad_s * 16000):int(vad_e * 16000)]
                        if len(sub_chunk) <= 1600: return []
                        
                        # [시니어 튜닝] Whisper 내부 VAD와 단어 단위 정밀 타임스탬프를 병행하여 숨소리/공백 싱크 밀림 원천 차단
                        transcribe_kwargs = dict(
                            beam_size=beam_size,
                            language=selected_lang,
                            vad_filter=use_whisper_vad,
                            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5) if use_whisper_vad else None,
                            condition_on_previous_text=False,
                            # [발음 정확도] temperature=0.0 단일값 대신 fallback 리스트 사용
                            # 첫 시도(0.0)에서 확신도 낮으면 0.2→0.4 순서로 자동 재시도 (Whisper 공식 방식)
                            temperature=[0.0, 0.2, 0.4],
                            # [발음 정확도] 반복 패널티: 같은 발음을 우물쭈물 반복하는 오인식 억제
                            repetition_penalty=1.1,
                            # [발음 정확도] 무음 판정 임계값을 낮춰 작은 목소리/짧은 발화도 포착
                            no_speech_threshold=0.45,
                            # [발음 정확도] 반복성 텍스트 조기 감지 기준 강화
                            compression_ratio_threshold=2.2,
                            word_timestamps=use_word_timestamps
                        )
                            
                        segs, _ = model.transcribe(sub_chunk, **transcribe_kwargs)
                        segs_list = list(segs)
                        
                        sub_max_time = vad_e - vad_s
                        offset_vad = offset + vad_s
                        
                        # --- [500년 뱀파이어 절기] 물리적 절대 록온 (Absolute Physical Sync Lock-on) ---
                        if use_silero_vad:
                            pad_sec = speech_pad_ms / 1000.0
                            vad_true_start = min(pad_sec, sub_max_time)
                            vad_true_end = max(sub_max_time - pad_sec, 0.0)
                            
                            window_size = 160 # 10ms
                            if len(sub_chunk) >= window_size:
                                n_windows = len(sub_chunk) // window_size
                                windows = sub_chunk[:n_windows * window_size].reshape(n_windows, window_size)
                                energies = np.sqrt(np.mean(windows**2, axis=1))
                                max_nrg = np.max(energies)
                                if max_nrg > 0.001:
                                    thresh = max(0.001, max_nrg * 0.03) 
                                    for idx in range(n_windows):
                                        if energies[idx] > thresh:
                                            vad_true_start = max(vad_true_start, max(0, idx - 1) * 0.01)
                                            break
                                    for idx in range(n_windows - 1, -1, -1):
                                        if energies[idx] > thresh:
                                            vad_true_end = min(vad_true_end, min(n_windows - 1, idx + 1) * 0.01)
                                            break
                        else:
                            vad_true_start = 0.0
                            vad_true_end = sub_max_time
                        # -----------------------------------------------------------------------------
                        
                        num_segs = len(segs_list)
                        extracted_results = []
                        
                        for i, s in enumerate(segs_list):
                            if stop_event.is_set(): break
                            text = s.text.strip()
                            if getattr(options, 'remove_punctuation', False):
                                import re
                                text = re.sub(r'[.,\-]', '', text).strip()
                            if not text: continue
                            
                            seg_s = s.start
                            seg_e = s.end
                            
                            if i == 0: seg_s = vad_true_start
                            if i == num_segs - 1: seg_e = vad_true_end
                            
                            seg_s = max(vad_true_start, seg_s)
                            seg_e = min(vad_true_end, seg_e)
                            if seg_e <= seg_s: seg_s, seg_e = vad_true_start, vad_true_end

                            if s.words:
                                extracted = []
                                curr_words = []
                                curr_s = min(seg_s, s.words[0].start) if i != 0 else seg_s
                                last_e = curr_s
                                
                                for w_idx, w in enumerate(s.words):
                                    w_s = max(seg_s, min(w.start, seg_e))
                                    w_e = max(w_s, min(w.end, seg_e))
                                    if i == num_segs - 1 and w_idx == len(s.words) - 1:
                                        w_e = seg_e 
                                        
                                    word_str = w.word
                                    if getattr(options, 'remove_punctuation', False):
                                        import re
                                        word_str = re.sub(r'[.,\-]', '', word_str)
                                        
                                    if w_s - last_e > split_gap_sec:
                                        t = "".join(w.word for w in curr_words).strip()
                                        if t and last_e > curr_s: extracted.append(TranscriptSegment(s=offset_vad + curr_s, e=offset_vad + last_e, t=t, words=curr_words))
                                        curr_words, curr_s = [TranscriptWord(word=word_str, s=offset_vad + w_s, e=offset_vad + w_e)], w_s
                                    else:
                                        curr_words.append(TranscriptWord(word=word_str, s=offset_vad + w_s, e=offset_vad + w_e))
                                    last_e = w_e
                                    
                                t = "".join(w.word for w in curr_words).strip()
                                if t and last_e > curr_s: extracted.append(TranscriptSegment(s=offset_vad + curr_s, e=offset_vad + last_e, t=t, words=curr_words))
                                
                                for ex in extracted: extracted_results.append(ex)
                            else:
                                c_s, c_e = min(seg_s, sub_max_time), min(seg_e, sub_max_time)
                                if c_e > c_s: extracted_results.append(TranscriptSegment(s=offset_vad + c_s, e=min(offset_vad + c_e, total_dur), t=text, words=[TranscriptWord(word=text, s=offset_vad + c_s, e=min(offset_vad + c_e, total_dur))]))
                                
                        return extracted_results

                    raw_results = []
                    # [시니어 최적화] 블로킹 없는 ThreadPoolExecutor 셧다운 도입
                    # ThreadPoolExecutor와 Whisper의 worker 수를 1:1 매칭 (오버헤드 방지)
                    active_workers = 2 if self._detect_best_device(device_mode) == "cpu" else 1
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=active_workers)
                    try:
                        # map 대신 submit을 사용하여 개별 퓨처 제어
                        futures = [executor.submit(_process_ts, bounds) for bounds in safe_tss]
                        for fut in futures:
                            if stop_event.is_set(): break
                            raw_results.extend(fut.result())
                    finally:
                        executor.shutdown(wait=False)
                    
                    # [시니어 추가] 주인공 목소리 필터링 적용
                    if use_dominant and len(raw_results) > 0:
                        raw_results = self.filter_dominant_speaker(audio_data, raw_results)
                        
                    for r in raw_results:
                        if stop_event.is_set(): break
                        text = r.t if isinstance(r, TranscriptSegment) else r['t']
                        r_s = r.s if isinstance(r, TranscriptSegment) else r['s']
                        r_e = r.e if isinstance(r, TranscriptSegment) else r['e']
                        
                        clean_text = TextSanitizer.clean_special_chars(text)
                        
                        if not TextSanitizer.is_valid_language(text, clean_text, selected_lang):
                            continue
                            
                        if TextSanitizer.is_youtube_outro_hallucination(text, clean_text):
                            continue
                            
                        if TextSanitizer.is_looping_hallucination(clean_text):
                            # [시니어 재생성 알고리즘] 버리기 전에 해당 오디오 구간만 다시 추출하여 파라미터 변조 후 구출 시도
                            s_idx, e_idx = max(0, int((r_s - offset) * 16000)), min(len(chunk), int((r_e - offset) * 16000))
                            if e_idx > s_idx:
                                regen_segs, _ = model.transcribe(
                                    chunk[s_idx:e_idx],
                                    beam_size=1,             # Beam Search 비활성화 (Greedy 방식 사용)
                                    language=selected_lang,
                                    temperature=0.8,         # Temperature(온도)를 대폭 올려 반복 확률 완전 차단
                                    condition_on_previous_text=False,
                                    vad_filter=False
                                )
                                regen_t = " ".join([rs.text.strip() for rs in regen_segs]).strip()
                                regen_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', regen_t)
                                
                                # 재생성 결과가 정상적이면 기존 값을 덮어쓰고 살려냄
                                if len(regen_clean) > 0 and (len(set(regen_clean)) / len(regen_clean) > 0.4):
                                    if isinstance(r, TranscriptSegment):
                                        r.t = regen_t
                                        r.words = [TranscriptWord(word=regen_t, s=r_s, e=r_e)]
                                    else:
                                        r['t'] = regen_t
                                        r['words'] = [{'word': regen_t, 's': r_s, 'e': r_e}]
                                    yield r
                            continue # 재생성도 실패하거나 못 살리면 최종적으로 버림 (Drop)
                        
                        if isinstance(r, dict) and 'words' not in r: r['words'] = [{'word': r['t'], 's': r['s'], 'e': r['e']}]
                        yield r
                
                gc.collect()
                start_idx = end_idx
                # --- [추가] 물리적 오디오 처리 위치 기반 진행률 강제 보고 ---
                yield {"is_heartbeat": True, "progress": (start_idx / total_samples) * 100}
        
        return safe_generator(), total_dur
