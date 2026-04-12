import os
import sys
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
import json
from collections import Counter
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps
import imageio_ffmpeg
import concurrent.futures
from dataclasses import dataclass
from config_models import AnalysisSettings, TranscriptSegment, TranscriptWord
from text_sanitizer import TextSanitizer
from audio_processor import AudioProcessor
from vision_processor import VisionProcessor
from transcription_backends import backend_kind

try:
    from pywhispercpp.model import Model as WhisperCppModel
    HAS_PYWHISPERCPP = True
except ImportError:
    WhisperCppModel = None
    HAS_PYWHISPERCPP = False
# [시니어] WhisperX 정밀 정렬 (Optional Dependency)
try:
    import whisperx
    import whisperx.utils
    try:
        import nltk
        _nltk_paths = [
            os.path.join(os.getcwd(), ".venv", "nltk_data"),
            os.path.join(os.path.dirname(__file__), ".venv", "nltk_data"),
            os.path.join(os.path.dirname(__file__), "nltk_data"),
        ]
        for _p in _nltk_paths:
            if os.path.isdir(_p) and _p not in nltk.data.path:
                nltk.data.path.insert(0, _p)
    except Exception:
        pass
    HAS_WHISPERX = True
    # [시니어] WhisperX 한국어 띄어쓰기 삭제 버그 우회 (Monkey Patch)
    if hasattr(whisperx.utils, "LANGUAGES_WITHOUT_SPACES") and "ko" in whisperx.utils.LANGUAGES_WITHOUT_SPACES:
        whisperx.utils.LANGUAGES_WITHOUT_SPACES.remove("ko")
except ImportError:
    HAS_WHISPERX = False
    print("[WARN] WhisperX module not found. Forced alignment feature is disabled.")

@dataclass
class RuntimeWord:
    word: str
    start: float
    end: float


@dataclass
class RuntimeSegment:
    text: str
    start: float
    end: float
    words: list


MODEL_SPECS = {
    "large-v3-turbo": {
        "bundled_fw_dir": "faster-whisper-large-v3-turbo",
        "torch_model": "openai/whisper-large-v3-turbo",
        "whispercpp_model": "large-v3-turbo",
    },
    "medium": {
        "bundled_fw_dir": "faster-whisper-medium",
        "torch_local_dir": "transformers-whisper-medium",
        "torch_model": "openai/whisper-medium",
        "whispercpp_model": "medium-q5_0",
    },
}

class HyperTranscriptionEngine:
    def __init__(self):
        self.base_dir = self._get_base_dir()
        self.model_id = "large-v3-turbo"
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.fw_model = None
        self.torch_whisper_pipe = None
        self.torch_whisper_key = None
        self.whispercpp_model = None
        self.whispercpp_key = None
        self.coreml_runtime_ready = None
        self.mps_segment_fallback_warned = False
        self.vad_model = None
        self.vad_device_info = None
        self.vision_processor = VisionProcessor(self._detect_best_device)
        self.clip_processor = None
        
        # [시니어 최적화] 하드웨어 코어의 50%만 동적으로 계산하여 할당 (100% 점유 방지)
        total_cores = os.cpu_count() or 4
        self.cpu_cores = max(1, int(total_cores * 0.5))
        self.device_info = "auto"
        self.align_models_cache = {}    # [캐싱] (언어, 디바이스)별 WhisperX 정렬 모델
        self.gemma4_mlx_model = None
        self.gemma4_mlx_processor = None
        self.gemma4_mlx_model_id = None
        self.gemma4_mlx_warned = False

    @staticmethod
    def _should_fallback_short_whisperx_segment(orig_seg, aligned_seg):
        """Use original timings when WhisperX over-compresses very short utterances.

        This is intentionally conservative so longer lines keep their improved starts.
        """
        orig_duration = max(0.0, float(orig_seg.end) - float(orig_seg.start))
        aligned_duration = max(0.0, float(aligned_seg.end) - float(aligned_seg.start))
        if orig_duration <= 0.0 or aligned_duration <= 0.0:
            return False
        if orig_duration > 1.8:
            return False
        if aligned_duration >= 0.9:
            return False
        if aligned_duration >= (orig_duration * 0.7):
            return False
        if (orig_duration - aligned_duration) < 0.18:
            return False
        return True

    @staticmethod
    def _should_review_with_gemma4_text(text):
        if not text:
            return False
        text = str(text).strip()
        if len(text) < 2:
            return True

        tokens = [tok for tok in re.split(r"\s+", text) if tok]
        if len(tokens) >= 3 and len(set(tokens)) == 1:
            return True

        normalized = re.sub(r"[\s\W_]+", "", text)
        if len(normalized) < 2:
            return True

        if len(normalized) >= 6:
            half = len(normalized) // 2
            if half > 0 and normalized[:half] == normalized[half:half * 2]:
                return True

        if re.search(r"(.)\1{5,}", normalized):
            return True

        if re.search(r"(.{2,12})\s+\1(\s+\1)+", text):
            return True

        return False

    def _get_gemma4_mlx_model_id(self):
        return os.environ.get("MLX_GEMMA4_MODEL", "mlx-community/gemma-4-e4b-it-8bit")

    def _ensure_gemma4_mlx_runtime(self):
        model_id = self._get_gemma4_mlx_model_id()
        if (
            self.gemma4_mlx_model is not None
            and self.gemma4_mlx_processor is not None
            and self.gemma4_mlx_model_id == model_id
        ):
            return self.gemma4_mlx_model, self.gemma4_mlx_processor

        try:
            from mlx_vlm import load
        except Exception as e:
            if not self.gemma4_mlx_warned:
                print(f"[WARN] Gemma 4 MLX runtime unavailable: {e}")
                self.gemma4_mlx_warned = True
            return None, None

        try:
            model, processor = load(model_id)
            self.gemma4_mlx_model = model
            self.gemma4_mlx_processor = processor
            self.gemma4_mlx_model_id = model_id
            return model, processor
        except Exception as e:
            if not self.gemma4_mlx_warned:
                print(f"[WARN] Gemma 4 MLX model load failed ({model_id}): {e}")
                self.gemma4_mlx_warned = True
            return None, None

    def _review_with_gemma4_mlx(self, text):
        model, processor = self._ensure_gemma4_mlx_runtime()
        if model is None or processor is None:
            return None

        prompt = processor.apply_chat_template(
            [{
                "role": "user",
                "content": (
                    "다음 한국어 자막 세그먼트가 정상 대사인지 판정해. "
                    "짧거나 구어체라도 정상 대사면 KEEP. "
                    "반복 환각, 의미 없는 잡음, 명백한 가비지면 DROP. "
                    "KEEP 또는 DROP만 답해.\n"
                    f"세그먼트: {text}"
                ),
            }],
            add_generation_prompt=True,
        )

        try:
            from mlx_vlm import generate
            result = generate(model, processor, prompt=prompt, verbose=False, max_tokens=8)
            output = (getattr(result, "text", "") or "").strip().upper()
            clean = re.sub(r"[^A-Z]", "", output)
            if "DROP" in clean:
                return False
            if "KEEP" in clean:
                return True
        except Exception as e:
            if not self.gemma4_mlx_warned:
                print(f"[WARN] Gemma 4 MLX inference failed: {e}")
                self.gemma4_mlx_warned = True
        return None

    def _filter_segments_with_gemma4_mlx(self, segs_list):
        filtered = []
        for seg in segs_list:
            text = getattr(seg, "text", "") or ""
            if not self._should_review_with_gemma4_text(text):
                filtered.append(seg)
                continue

            verdict = self._review_with_gemma4_mlx(text)
            if verdict is False:
                print(f"[INFO] Gemma 4 MLX filter dropped suspicious segment: {text[:80]}")
                continue
            filtered.append(seg)
        return filtered

    def release_runtime_memory(self):
        """Release backend/model objects so long-running sessions do not accumulate memory across analyses."""
        try:
            self.fw_model = None
            self.torch_whisper_pipe = None
            self.torch_whisper_key = None
            self.whispercpp_model = None
            self.whispercpp_key = None
            self.vad_model = None
            self.vad_device_info = None
            self.align_models_cache.clear()
            self.mps_segment_fallback_warned = False
            self.gemma4_mlx_model = None
            self.gemma4_mlx_processor = None
            self.gemma4_mlx_model_id = None
            self.gemma4_mlx_warned = False

            if hasattr(self.vision_processor, "clip_model"):
                self.vision_processor.clip_model = None
            if hasattr(self.vision_processor, "clip_processor"):
                self.vision_processor.clip_processor = None
            if hasattr(self.vision_processor, "clip_model_key"):
                self.vision_processor.clip_model_key = None
            if hasattr(AudioProcessor, "release_cached_models"):
                AudioProcessor.release_cached_models()

            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception as e:
            print(f"[WARN] release_runtime_memory failed: {e}")

    def release_analysis_memory(self):
        """Drop per-analysis caches without forcing full model reload during the same run."""
        try:
            if hasattr(AudioProcessor, "release_cached_models"):
                AudioProcessor.release_cached_models()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception as e:
            print(f"[WARN] release_analysis_memory failed: {e}")
        
    def _get_base_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def _resolve_model_id(self, model_id):
        if not model_id:
            return model_id

        normalized = model_id.replace("/", os.sep)
        candidate_paths = []
        if not os.path.isabs(normalized):
            candidate_paths.append(os.path.join(self.base_dir, normalized))
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidate_paths.append(os.path.join(meipass, normalized))
        else:
            candidate_paths.append(normalized)

        spec = MODEL_SPECS.get(model_id)
        bundled_fw_dir = spec.get("bundled_fw_dir") if spec else None
        if bundled_fw_dir:
            for root_dir in (self.base_dir, getattr(sys, "_MEIPASS", None)):
                if not root_dir:
                    continue
                bundled_path = os.path.join(root_dir, "models", bundled_fw_dir)
                if os.path.isdir(bundled_path):
                    print(f"[INFO] Using bundled {model_id} model: {bundled_path}")
                    return bundled_path

        for candidate in candidate_paths:
            if os.path.isdir(candidate):
                return candidate

        return model_id

    def _detect_best_device(self, user_choice="auto"):
        """[??? ???? ??] ??? ?? ?? ?? ?? ?? ??"""
        if user_choice == "coreml":
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
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

    def _get_torch_whisper_model_name(self):
        spec = MODEL_SPECS.get(self.model_id, {})
        local_dir = spec.get("torch_local_dir")
        if local_dir:
            for root_dir in (self.base_dir, getattr(sys, "_MEIPASS", None)):
                if not root_dir:
                    continue
                local_path = os.path.join(root_dir, "models", local_dir)
                if os.path.isdir(local_path):
                    return local_path
        return spec.get("torch_model")

    def _get_whispercpp_model_name(self):
        spec = MODEL_SPECS.get(self.model_id, {})
        return spec.get("whispercpp_model")

    def _get_whispercpp_models_dir(self):
        return os.path.join(self.base_dir, "models", "whispercpp-coreml")

    def _get_whispercpp_model_path(self):
        model_name = self._get_whispercpp_model_name()
        if model_name is None:
            return None
        return os.path.join(self._get_whispercpp_models_dir(), f"ggml-{model_name}.bin")

    def _use_torch_whisper_backend(self, device_mode="auto"):
        return backend_kind(device_mode) == "mps" and self._detect_best_device(device_mode) == "mps" and self._get_torch_whisper_model_name() is not None

    def _use_coreml_backend(self, device_mode="auto"):
        return backend_kind(device_mode) == "coreml"

    def _fallback_medium_device_mode(self, requested_mode, reason):
        backend = backend_kind(requested_mode)
        if self.model_id != "medium" or backend not in {"mps", "coreml"}:
            return requested_mode, False
        fallback_mode = "cpu_50"
        print(f"[WARN] Falling back to {fallback_mode} for medium model from {requested_mode}: {reason}")
        return fallback_mode, True

    def _detect_coreml_runtime(self):
        if self.coreml_runtime_ready is not None:
            return self.coreml_runtime_ready
        if not HAS_PYWHISPERCPP:
            self.coreml_runtime_ready = False
            return self.coreml_runtime_ready
        info = WhisperCppModel.system_info()
        self.coreml_runtime_ready = "COREML = 1" in info
        return self.coreml_runtime_ready

    def _get_torch_whisper_pipeline(self, device_mode="auto"):
        model_name = self._get_torch_whisper_model_name()
        if model_name is None:
            raise ValueError(f"MPS transcription backend does not support model '{self.model_id}'.")

        cache_key = (model_name, "mps")
        if self.torch_whisper_pipe is None or self.torch_whisper_key != cache_key:
            from transformers import pipeline

            self.torch_whisper_pipe = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device="mps",
                dtype=torch.float32,
            )
            self.torch_whisper_key = cache_key
            print(f"[INFO] Using torch Whisper pipeline on MPS: {model_name}")
        return self.torch_whisper_pipe

    def get_model(self, device_mode="auto"):
        if self._use_torch_whisper_backend(device_mode):
            return self._get_torch_whisper_pipeline(device_mode)
        if self._use_coreml_backend(device_mode):
            return None

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
            
            model_source = self._resolve_model_id(self.model_id)
            self.fw_model = WhisperModel(model_source, device=ct2_dev, compute_type=c_type, cpu_threads=threads_per_worker, num_workers=workers)
        return self.fw_model

    def _transcribe_with_torch_whisper(self, audio_chunk, selected_lang, use_word_timestamps):
        pipe = self._get_torch_whisper_pipeline("mps")
        generate_kwargs = {
            "task": "transcribe",
            "num_beams": 1,
        }
        if selected_lang:
            generate_kwargs["language"] = selected_lang
        # transformers Whisper word timestamps are unstable on Korean in the current MPS path.
        # Use segment timestamps for the mac Metal backend and let downstream code create
        # coarse word blocks when needed, rather than crashing mid-analysis.
        if use_word_timestamps and not self.mps_segment_fallback_warned:
            print("[WARN] MPS backend is using segment timestamps fallback instead of word timestamps.")
            self.mps_segment_fallback_warned = True
        result = pipe(
            np.asarray(audio_chunk, dtype=np.float32),
            return_timestamps=True,
            generate_kwargs=generate_kwargs,
        )
        use_word_timestamps = False

        text = (result.get("text") or "").strip()
        if not text:
            return []

        if not use_word_timestamps:
            chunk_segments = []
            for chunk in result.get("chunks", []):
                seg_text = (chunk.get("text") or "").strip()
                timestamp = chunk.get("timestamp") or ()
                if not seg_text or len(timestamp) != 2:
                    continue
                seg_start, seg_end = timestamp
                if seg_start is None or seg_end is None or seg_end <= seg_start:
                    continue
                chunk_segments.append(
                    RuntimeSegment(
                        text=seg_text,
                        start=float(seg_start),
                        end=float(seg_end),
                        words=[],
                    )
                )
            if chunk_segments:
                return chunk_segments

        if use_word_timestamps:
            words = []
            for chunk in result.get("chunks", []):
                word = (chunk.get("text") or "").strip()
                timestamp = chunk.get("timestamp") or ()
                if not word or len(timestamp) != 2:
                    continue
                w_start, w_end = timestamp
                if w_start is None or w_end is None or w_end <= w_start:
                    continue
                words.append(RuntimeWord(word=word, start=float(w_start), end=float(w_end)))

            if words:
                merged_text = " ".join(w.word for w in words).strip()
                return [RuntimeSegment(text=merged_text or text, start=words[0].start, end=words[-1].end, words=words)]

        duration = len(audio_chunk) / 16000.0
        return [RuntimeSegment(text=text, start=0.0, end=duration, words=[])]

    def _get_whispercpp_model(self, device_mode="coreml"):
        if not HAS_PYWHISPERCPP:
            raise RuntimeError("pywhispercpp is not installed.")

        model_name = self._get_whispercpp_model_name()
        if model_name is None:
            raise ValueError(f"whisper.cpp backend does not support model '{self.model_id}'.")

        model_path = self._get_whispercpp_model_path()
        coreml_bundle = os.path.join(
            self._get_whispercpp_models_dir(),
            f"ggml-{model_name}-encoder.mlmodelc",
        )
        if not os.path.isfile(model_path):
            raise RuntimeError(
                f"whisper.cpp model file is missing: {model_path}"
            )
        if not os.path.isdir(coreml_bundle):
            raise RuntimeError(
                f"whisper.cpp Core ML bundle is missing: {coreml_bundle}"
            )

        if not self._detect_coreml_runtime():
            raise RuntimeError(
                "whisper.cpp runtime is installed, but Core ML support is not enabled "
                "(current system_info reports COREML = 0)."
            )

        threads = self._get_target_cores(device_mode)
        cache_key = (model_path, threads, "coreml")
        if self.whispercpp_model is None or self.whispercpp_key != cache_key:
            self.whispercpp_model = WhisperCppModel(
                model=model_path,
                models_dir=self._get_whispercpp_models_dir(),
                n_threads=threads,
                print_realtime=False,
                print_progress=False,
                print_timestamps=False,
            )
            self.whispercpp_key = cache_key
            print(f"[INFO] Using whisper.cpp Core ML backend: {model_path}")
        return self.whispercpp_model

    def _transcribe_with_coreml(self, audio_chunk, selected_lang, use_word_timestamps, use_worker=False):
        if os.environ.get("VIBE_COREML_CHILD") == "1":
            return self._transcribe_with_coreml_local(audio_chunk, selected_lang, use_word_timestamps)
        if use_worker:
            return self._transcribe_with_coreml_subprocess(audio_chunk, selected_lang, use_word_timestamps)
        return self._transcribe_with_coreml_local(audio_chunk, selected_lang, use_word_timestamps)

    def _transcribe_with_coreml_local(self, audio_chunk, selected_lang, use_word_timestamps):
        model = self._get_whispercpp_model("coreml")
        params = {
            "language": selected_lang or "auto",
            "translate": False,
            "max_len": 0,
        }
        segments = model.transcribe(np.asarray(audio_chunk, dtype=np.float32), token_timestamps=False, **params)
        runtime_segments = []
        for seg in segments:
            text = (seg.text or "").strip()
            if not text:
                continue
            runtime_segments.append(
                RuntimeSegment(
                    text=text,
                    start=float(seg.t0) / 100.0,
                    end=float(seg.t1) / 100.0,
                    words=[],
                )
            )

        if not use_word_timestamps or not runtime_segments:
            return runtime_segments

        # whisper.cpp CoreML 경로는 기본 세그먼트 결과에 단어 배열을 바로 주지 않으므로
        # token_timestamps + split_on_word + max_len=1 조합으로 word-like segments를 한 번 더 뽑아 words를 채운다.
        word_segments = model.transcribe(
            np.asarray(audio_chunk, dtype=np.float32),
            language=selected_lang or "auto",
            translate=False,
            token_timestamps=True,
            split_on_word=True,
            max_len=1,
        )
        runtime_words = []
        for seg in word_segments:
            text = (seg.text or "").strip()
            if not text:
                continue
            start = float(seg.t0) / 100.0
            end = float(seg.t1) / 100.0
            if end <= start:
                continue
            runtime_words.append(RuntimeWord(word=text, start=start, end=end))

        if not runtime_words:
            return runtime_segments

        word_idx = 0
        epsilon = 0.05
        for seg in runtime_segments:
            seg_words = []
            while word_idx < len(runtime_words) and runtime_words[word_idx].end <= seg.start - epsilon:
                word_idx += 1

            scan_idx = word_idx
            while scan_idx < len(runtime_words):
                word = runtime_words[scan_idx]
                if word.start >= seg.end + epsilon:
                    break
                mid = (word.start + word.end) / 2.0
                if (seg.start - epsilon) <= mid <= (seg.end + epsilon):
                    seg_words.append(word)
                scan_idx += 1

            seg.words = seg_words
        return runtime_segments

    def _transcribe_with_coreml_subprocess(self, audio_chunk, selected_lang, use_word_timestamps):
        worker_python = os.path.join(self.base_dir, ".venv", "bin", "python")
        if not os.path.isfile(worker_python):
            worker_python = sys.executable
        worker_script = os.path.join(self.base_dir, "tools", "coreml_transcribe_worker.py")
        if not os.path.isfile(worker_script):
            raise RuntimeError(f"CoreML worker script is missing: {worker_script}")

        temp_dir = tempfile.mkdtemp(prefix="vibe_coreml_worker_")
        input_path = os.path.join(temp_dir, "audio.npy")
        output_path = os.path.join(temp_dir, "segments.json")
        np.save(input_path, np.asarray(audio_chunk, dtype=np.float32))

        cmd = [worker_python, worker_script, "--model-id", self.model_id, "--input", input_path, "--output", output_path]
        if selected_lang:
            cmd.extend(["--language", selected_lang])
        if use_word_timestamps:
            cmd.append("--word-timestamps")

        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = self.base_dir if not existing_pythonpath else f"{self.base_dir}{os.pathsep}{existing_pythonpath}"
        env["VIBE_COREML_CHILD"] = "1"

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.base_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or "").strip() or f"CoreML worker exited with code {proc.returncode}")
            with open(output_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            runtime_segments = []
            for seg in payload:
                words = [
                    RuntimeWord(
                        word=w.get("word", ""),
                        start=float(w.get("start", 0.0)),
                        end=float(w.get("end", 0.0)),
                    )
                    for w in seg.get("words", [])
                    if w.get("word")
                ]
                runtime_segments.append(
                    RuntimeSegment(
                        text=seg.get("text", ""),
                        start=float(seg.get("start", 0.0)),
                        end=float(seg.get("end", 0.0)),
                        words=words,
                    )
                )
            return runtime_segments
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def set_model_id(self, new_model_id):
        if self.model_id != new_model_id:
            self.model_id = new_model_id
            self.release_runtime_memory()
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
            self.vad_device_info = "cpu"
                
        return self.vad_model

    def get_clip_model(self, device_mode="auto"):
        return self.vision_processor.get_clip_model(device_mode)

    def get_align_model(self, language_code="ko", device_mode="auto"):
        """WhisperX forced alignment 모델을 lazy load 및 캐싱"""
        if not HAS_WHISPERX:
            return None, None
            
        best_device = self._detect_best_device(device_mode)
        
        # [시니어] 언어 코드가 불분명하면 ko로 강제 매핑
        lang_code = language_code if language_code and language_code != "auto" else "ko"
        
        cache_key = (lang_code, best_device)

        if cache_key not in self.align_models_cache:
            try:
                print(f"[INFO] WhisperX alignment 모델 로딩 시작: {lang_code} ({best_device})")
                model_a, metadata = whisperx.load_align_model(language_code=lang_code, device=best_device)
                self.align_models_cache[cache_key] = (model_a, metadata)
            except Exception as e:
                print(f"[ERROR] WhisperX alignment 모델 로드 실패 ({lang_code}): {e}")
                return None, None
        
        return self.align_models_cache[cache_key]

    def load_audio_to_memory(self, video_path):
        return AudioProcessor.load_audio_to_memory(video_path, self.ffmpeg_exe)

    def probe_audio_duration(self, video_path):
        return AudioProcessor.probe_audio_duration(video_path, self.ffmpeg_exe)

    def iter_audio_chunks(self, video_path, chunk_duration_sec=600):
        return AudioProcessor.iter_audio_chunks(video_path, self.ffmpeg_exe, chunk_duration_sec=chunk_duration_sec)

    def detect_speech_vad_stream(self, audio_data, stop_event, min_silence_ms=2000, speech_pad_ms=250, options=None):
        if options is None:
            device_mode = "auto"
            vad_threshold = 0.35
        elif isinstance(options, dict):
            device_mode = options.get("device_mode", "auto")
            vad_threshold = options.get("vad_threshold", 0.35)
        else:
            device_mode = getattr(options, "device_mode", "auto")
            vad_threshold = getattr(options, "vad_threshold", 0.35)
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

    def separate_vocals_demucs(self, audio_data):
        return AudioProcessor.separate_vocals_demucs(audio_data)

    def filter_dominant_speaker(self, audio_data, segments):
        return AudioProcessor.filter_dominant_speaker(audio_data, segments)

    def transcribe_stream_raw(self, audio_data, stop_event, options: AnalysisSettings = None):
        if options is None: options = AnalysisSettings()
        device_mode = options.device_mode
        device_mode, _ = self._fallback_medium_device_mode(
            device_mode,
            "medium backend is currently stabilized on the CPU path in this build",
        )
        try:
            model = self.get_model(device_mode)
        except Exception as e:
            device_mode, did_fallback = self._fallback_medium_device_mode(device_mode, e)
            if not did_fallback:
                raise
            model = self.get_model(device_mode)
        
        beam_size = options.beam_size
        use_denoise = options.use_denoise
        use_demucs = getattr(options, "use_demucs", False)
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
        use_coreml_worker = getattr(options, "use_coreml_worker", False)
        runtime_whisper_vad = {"enabled": use_whisper_vad}
        use_whisperx_align = options.use_whisperx_align
        use_whisperx_short_fallback = getattr(options, "use_whisperx_short_fallback", False)
        use_gemma4_mlx_filter = getattr(options, "use_gemma4_mlx_filter", False)
        use_word_timestamps = use_word_timestamps or use_whisperx_align or use_whisperx_short_fallback

        if use_demucs:
            audio_data = self.separate_vocals_demucs(audio_data)

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
                            vad_filter=runtime_whisper_vad["enabled"],
                            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5) if runtime_whisper_vad["enabled"] else None,
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
                            
                        try:
                            if self._use_coreml_backend(device_mode):
                                segs_list = self._transcribe_with_coreml(sub_chunk, selected_lang, use_word_timestamps, use_worker=use_coreml_worker)
                            elif self._use_torch_whisper_backend(device_mode):
                                segs_list = self._transcribe_with_torch_whisper(sub_chunk, selected_lang, use_word_timestamps)
                            else:
                                segs, _ = model.transcribe(sub_chunk, **transcribe_kwargs)
                                segs_list = list(segs)
                        except Exception as e:
                            err_text = str(e).lower()
                            if (not self._use_torch_whisper_backend(device_mode)) and (not self._use_coreml_backend(device_mode)) and runtime_whisper_vad["enabled"] and any(token in err_text for token in ["onnx", "vad", "ort"]):
                                runtime_whisper_vad["enabled"] = False
                                print(f"[WARN] Whisper VAD failed, retrying without internal VAD: {e}")
                                transcribe_kwargs["vad_filter"] = False
                                transcribe_kwargs["vad_parameters"] = None
                                segs, _ = model.transcribe(sub_chunk, **transcribe_kwargs)
                                segs_list = list(segs)
                            else:
                                raise
                        
                        # [WhisperX] WhisperX forced alignment로 단어 타임스탬프 보정
                        if HAS_WHISPERX and use_whisperx_align and use_word_timestamps and segs_list:
                            try:
                                best_dev = self._detect_best_device(device_mode)
                                model_a, metadata = self.get_align_model(selected_lang, device_mode)
                                
                                if model_a is not None:
                                    # [시니어] 특수기호 에러 우회: 순수 텍스트만 추출하여 전달
                                    wx_segments = []
                                    for s in segs_list:
                                        # 한글, 영어, 숫자, 공백 제외 모두 제거
                                        clean_txt = re.sub(r'[^\w\s가-힣]', '', s.text).strip()
                                        wx_segments.append({
                                            "text": clean_txt if clean_txt else s.text.strip(),
                                            "start": s.start,
                                            "end": s.end
                                        })
                                    
                                    # 정렬 실행 (글자 단위 정밀 정렬 활성화)
                                    aligned_result = whisperx.align(
                                        wx_segments, 
                                        model_a, 
                                        metadata, 
                                        sub_chunk, 
                                        best_dev, 
                                        return_char_alignments=True
                                    )
                                    
                                    # 기존 래퍼 클래스 규격에 맞춰 복구 (AttributeError 방지)
                                    class _CTCAlignedSeg:
                                        def __init__(self, orig_seg, new_words):
                                            self.text = orig_seg.get("text", "")
                                            self.start = orig_seg.get("start", 0.0)
                                            self.end = orig_seg.get("end", 0.0)
                                            class _W:
                                                def __init__(self, word, s, e):
                                                    self.word = word
                                                    self.start = s
                                                    self.end = e
                                            self.words = [_W(w['word'], w['start'], w['end']) for w in new_words]

                                    aligned_segments = aligned_result.get("segments", [])
                                    if len(aligned_segments) != len(segs_list):
                                        print(f"[WARN] WhisperX segment count mismatch: aligned={len(aligned_segments)}, original={len(segs_list)}. Falling back safely.")

                                    new_segs = []
                                    for i, seg_dict in enumerate(aligned_segments):
                                        # Preserve timing even when WhisperX returns fewer or more segments.
                                        orig_seg = segs_list[i] if i < len(segs_list) else None
                                        orig_words = getattr(orig_seg, 'words', []) or []
                                        raw_words = seg_dict.get("words", [])
                                        
                                        new_words_data = []
                                        last_processed_e = seg_dict.get("start", 0.0)
                                        
                                        for w_idx, w in enumerate(raw_words):
                                            # 1. 텍스트 및 기본 폴백 시간 확보 (원본 Faster-Whisper 데이터 참조)
                                            if w_idx < len(orig_words):
                                                orig_w = orig_words[w_idx]
                                                w_word = orig_w.word
                                                fback_s, fback_e = orig_w.start, orig_w.end
                                            else:
                                                w_word = w.get("word", "")
                                                fback_s = last_processed_e + 0.02
                                                fback_e = fback_s + 0.15

                                            # 2. 글자 배열(chars)에서 정밀 시작/종료 시간 추출
                                            char_list = w.get("chars", [])
                                            valid_chars = [c for c in char_list if "start" in c and "end" in c]
                                            
                                            if valid_chars:
                                                # [정밀] 첫 글자의 시작과 마지막 글자의 종료 시간 사용
                                                w_start = valid_chars[0]["start"]
                                                w_end = valid_chars[-1]["end"]
                                            else:
                                                # [Fallback 1] 단어 단위 시간 정보 사용
                                                # [Fallback 2] 원본 Faster-Whisper 시간 혹은 상대 오프셋 사용
                                                w_start = w.get("start", fback_s)
                                                w_end = w.get("end", fback_e)
                                            
                                            new_words_data.append({"word": w_word, "start": w_start, "end": w_end})
                                            last_processed_e = w_end
                                        
                                        aligned_seg = _CTCAlignedSeg(seg_dict, new_words_data)
                                        if (
                                            use_whisperx_short_fallback
                                            and orig_seg is not None
                                            and self._should_fallback_short_whisperx_segment(orig_seg, aligned_seg)
                                        ):
                                            new_segs.append(orig_seg)
                                        else:
                                            new_segs.append(aligned_seg)

                                    if len(aligned_segments) < len(segs_list):
                                        new_segs.extend(segs_list[len(aligned_segments):])

                                    if new_segs:
                                        segs_list = new_segs
                                    
                            except Exception as e:
                                print(f"[WARN] WhisperX alignment 전체 실패, 기존 결과 유지: {e}")

                        if use_gemma4_mlx_filter and segs_list:
                            segs_list = self._filter_segments_with_gemma4_mlx(segs_list)
                        
                        sub_max_time = vad_e - vad_s
                        offset_vad = offset + vad_s
                        
                        # --- [500년 뱀파이어 절기] 물리적 절대 록온 (Absolute Physical Sync Lock-on) ---
                        # [시니어] WhisperX 정밀 싱크가 활성화된 경우 이 로직을 우회하여 보정값 훼손을 방지함
                        if use_silero_vad and not use_whisperx_align:
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
                                        word_str = re.sub(r'[.,\-]', '', word_str)
                                        
                                    if w_s - last_e > split_gap_sec:
                                        t = " ".join(w.word.strip() for w in curr_words).strip()
                                        if t and last_e > curr_s: extracted.append(TranscriptSegment(s=offset_vad + curr_s, e=offset_vad + last_e, t=t, words=curr_words))
                                        curr_words, curr_s = [TranscriptWord(word=word_str, s=offset_vad + w_s, e=offset_vad + w_e)], w_s
                                    else:
                                        curr_words.append(TranscriptWord(word=word_str, s=offset_vad + w_s, e=offset_vad + w_e))
                                    last_e = w_e
                                    
                                t = " ".join(w.word.strip() for w in curr_words).strip()
                                if t and last_e > curr_s: extracted.append(TranscriptSegment(s=offset_vad + curr_s, e=offset_vad + last_e, t=t, words=curr_words))
                                
                                for ex in extracted: extracted_results.append(ex)
                            else:
                                c_s, c_e = min(seg_s, sub_max_time), min(seg_e, sub_max_time)
                                if c_e > c_s:
                                    extracted_results.append(
                                        TranscriptSegment(
                                            s=offset_vad + c_s,
                                            e=min(offset_vad + c_e, total_dur),
                                            t=text,
                                            words=[],
                                        )
                                    )
                                
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
                        executor.shutdown(wait=True)
                    
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
                            can_regenerate = (
                                e_idx > s_idx
                                and (not self._use_torch_whisper_backend(device_mode))
                                and (not self._use_coreml_backend(device_mode))
                            )
                            if can_regenerate:
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
                                        r.words = []
                                    else:
                                        r['t'] = regen_t
                                        r['words'] = []
                                    yield r
                            continue # 재생성도 실패하거나 못 살리면 최종적으로 버림 (Drop)

                        if isinstance(r, dict) and 'words' not in r:
                            r['words'] = []
                        yield r
                
                gc.collect()
                start_idx = end_idx
                # --- [추가] 물리적 오디오 처리 위치 기반 진행률 강제 보고 ---
                yield {"is_heartbeat": True, "progress": (start_idx / total_samples) * 100}
        
        return safe_generator(), total_dur
