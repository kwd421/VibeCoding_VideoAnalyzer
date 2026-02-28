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

class HyperTranscriptionEngine:
    def __init__(self):
        self.model_id = "large-v3-turbo"
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.fw_model = None
        self.vad_model = None
        self.clip_model = None
        self.clip_processor = None
        
        # [시니어 최적화] 하드웨어 코어의 50%만 동적으로 계산하여 할당 (100% 점유 방지)
        total_cores = os.cpu_count() or 4
        self.cpu_cores = max(1, int(total_cores * 0.5))
        self.device_info = "auto"
        
    def _detect_best_device(self, user_choice="auto"):
        """[시니어 하드웨어 분석] 환경에 맞는 텐서 연산 장치 동적 스캔"""
        if user_choice != "auto":
            return user_choice
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    def get_model(self, device_mode="auto"):
        if self.fw_model is None or self.device_info != device_mode:
            self.device_info = device_mode
            best_device = self._detect_best_device(device_mode)
            
            # CTranslate2의 디바이스 맵핑 (cuda/cpu 외에는 fall back)
            ct2_dev = "cuda" if best_device == "cuda" else "cpu"
            c_type = "float16" if ct2_dev == "cuda" else "int8"
            
            self.fw_model = WhisperModel(self.model_id, device=ct2_dev, compute_type=c_type, cpu_threads=self.cpu_cores, num_workers=2)
        return self.fw_model

    def set_model_id(self, new_model_id):
        if self.model_id != new_model_id:
            self.model_id = new_model_id
            self.fw_model = None  # Force reload model

    def get_vad_model(self, device_mode="auto"):
        if self.vad_model is None:
            torch.set_num_threads(self.cpu_cores)
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
        """[시니어 최적화] CLIP 모델 Lazy Loading (필요할 때만 로드)"""
        if self.clip_model is None:
            model_name = "openai/clip-vit-base-patch32"
            best_dev = self._detect_best_device(device_mode)
            self.clip_model = CLIPModel.from_pretrained(model_name).to(best_dev)
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

    def detect_speech_vad_stream(self, audio_data, stop_event, min_silence_ms=2000, speech_pad_ms=250, options=None):
        options = options or {}
        device_mode = options.get("device_mode", "auto")
        model = self.get_vad_model(device_mode)
        sample_rate, chunk_size, overlap = 16000, 16000 * 60, 16000 * 2
        total_samples = len(audio_data)
        last_end_time = 0.0
        for i in range(0, total_samples, chunk_size):
            if stop_event.is_set(): break
            start, end = i, min(i + chunk_size + overlap, total_samples)
            tss = get_speech_timestamps(torch.from_numpy(audio_data[start:end]), model, sampling_rate=sample_rate, threshold=0.35, min_speech_duration_ms=150, min_silence_duration_ms=min_silence_ms, speech_pad_ms=speech_pad_ms)
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

    def detect_scenes_clip_stream(self, video_path, labels, stop_event, interval=10, options=None):
        """[시니어 최적화] CLIP 기반 제로샷 영상 분류 및 챕터 생성"""
        options = options or {}
        device_mode = options.get("device_mode", "auto")
        model, processor = self.get_clip_model(device_mode)
        device = self._detect_best_device(device_mode)
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

    def denoise_audio(self, audio_data):
        """[시니어 최적화] noisereduce를 이용한 고성능 배경 소음 제거 (Stationary Noise Reduction)"""
        try:
            # stationary=True: 배경 소음이 일정한 경우(선풍기, 에어컨 등)에 최적화
            denoised = nr.reduce_noise(y=audio_data, sr=16000, stationary=True, prop_decrease=0.75)
            return denoised
        except Exception as e:
            print(f"Denoise Error: {e}")
            return audio_data

    def filter_dominant_speaker(self, audio_data, segments):
        """[시니어 최적화] 에너지 기반 통계적 주인공 목소리 필터링 (RMS Thresholding)"""
        if not segments or len(segments) < 3: return segments
        
        energies = []
        for s in segments:
            start_i, end_i = int(s['s'] * 16000), int(s['e'] * 16000)
            chunk = audio_data[start_i:end_i]
            if len(chunk) > 0:
                energies.append(np.sqrt(np.mean(chunk**2)))
            else: energies.append(0)
            
        energies = np.array(energies)
        # [시니어 최적화] 주인공 목소리 필터 임계값 완화 (0.8 -> 0.4) 및 안정성 강화
        # 주인공이 계속 말을 할 때는 에너지가 유지되므로, 너무 엄격한 기준보다 최소 수준을 보장
        threshold = np.mean(energies) * 0.4
        
        filtered = [seg for i, seg in enumerate(segments) if energies[i] >= threshold]
        return filtered

    def transcribe_stream_raw(self, audio_data, stop_event, options=None):
        if options is None: options = {}
        device_mode = options.get("device_mode", "auto")
        model = self.get_model(device_mode)
        
        # 옵션 파싱 (기본값 설정)
        if options is None: options = {}
        beam_size = options.get("beam_size", 5)
        initial_prompt = options.get("initial_prompt", "")
        if not initial_prompt.strip(): initial_prompt = None
        use_denoise = options.get("use_denoise", False)
        use_dominant = options.get("use_dominant", False)
        selected_lang = options.get("language", "ko")
        if selected_lang == "auto": selected_lang = None
        vad_threshold = options.get("vad_threshold", 0.35)
        min_silence_ms = options.get("min_silence_ms", 2000)
        speech_pad_ms = options.get("speech_pad_ms", 250)
        split_gap_sec = max(1.0, min_silence_ms / 1000.0)
        use_word_timestamps = options.get("use_word_timestamps", True)
        use_whisper_vad = options.get("use_whisper_vad", True)
        use_silero_vad = options.get("use_silero_vad", True)

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
                        segs, _ = model.transcribe(
                            sub_chunk, 
                            beam_size=beam_size, 
                            initial_prompt=initial_prompt,
                            language=selected_lang, 
                            vad_filter=use_whisper_vad,
                            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5) if use_whisper_vad else None,
                            condition_on_previous_text=False, 
                            temperature=0.0,
                            word_timestamps=use_word_timestamps
                        )
                        
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
                        
                        segs_list = list(segs)
                        num_segs = len(segs_list)
                        extracted_results = []
                        
                        for i, s in enumerate(segs_list):
                            if stop_event.is_set(): break
                            text = s.text.strip()
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
                                        
                                    if w_s - last_e > split_gap_sec:
                                        t = "".join(curr_words).strip()
                                        if t and last_e > curr_s: extracted.append({'s': offset_vad + curr_s, 'e': offset_vad + last_e, 't': t})
                                        curr_words, curr_s = [w.word], w_s
                                    else:
                                        curr_words.append(w.word)
                                    last_e = w_e
                                    
                                t = "".join(curr_words).strip()
                                if t and last_e > curr_s: extracted.append({'s': offset_vad + curr_s, 'e': offset_vad + last_e, 't': t})
                                
                                for ex in extracted: extracted_results.append(ex)
                            else:
                                c_s, c_e = min(seg_s, sub_max_time), min(seg_e, sub_max_time)
                                if c_e > c_s: extracted_results.append({'s': offset_vad + c_s, 'e': min(offset_vad + c_e, total_dur), 't': text})
                                
                        return extracted_results

                    raw_results = []
                    # [시니어 최적화] 블로킹 없는 ThreadPoolExecutor 셧다운 도입
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
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
                        text = r['t']
                        # [시니어 헬퍼] 무의미한 환각(Hallucination) 쓰레기값 필터링 및 루핑 정지
                        clean_text = text.replace("쩜", "").replace("점", "").replace(".", "").replace(",", "").replace(" ", "").replace("~", "").replace("!", "").replace("?", "")
                        
                        # 1. 텍스트가 비어 있거나 부호만 있으면 드랍
                        if len(clean_text) < 1 and len(text) > 0: continue
                        
                        # [CRITICAL] Strict Language Bounding: 한국어를 선택했는데 한글([가-힣])이 단 한 글자도 없는 영어/외국어면 버림
                        if selected_lang == "ko" and re.search(r'[가-힣]', clean_text) is None: continue
                        
                        # 2. 고질적인 유튜브 아웃트로 환각 드랍
                        if any(h in text for h in ["시청해주셔서 감사합니다", "다음 영상에서 만나요", "구독과 좋아요", "시청해 주셔서 감사합니다"]):
                            if len(clean_text) < 15: continue
                            
                        # 3. [핵심] "뀨오오오오" 등 고비율 반복 파괴 버그 (Looping Hallucination) 차단
                        if len(clean_text) > 4:
                            unique_chars = len(set(clean_text))
                            repeat_ratio = unique_chars / len(clean_text) 
                            
                            # 글자 수가 7글자가 넘는데 종류가 3개 이하이거나, 전체 길이 대비 고유 문자 비율이 30% 이하라면 이상 현상으로 간주
                            if (unique_chars <= 3 and len(clean_text) >= 7) or (repeat_ratio <= 0.35 and len(clean_text) >= 9):
                                # [시니어 재생성 알고리즘] 버리기 전에 해당 오디오 구간만 다시 추출하여 파라미터 변조 후 구출 시도
                                s_idx, e_idx = max(0, int((r['s'] - offset) * 16000)), min(len(chunk), int((r['e'] - offset) * 16000))
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
                                        r['t'] = regen_t
                                        yield r
                                continue # 재생성도 실패하거나 못 살리면 최종적으로 버림 (Drop)
                        
                        yield r
                
                gc.collect()
                start_idx = end_idx
        
        return safe_generator(), total_dur
