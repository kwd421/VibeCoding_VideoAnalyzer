import os
import torch
import glob
import tempfile
import shutil
import subprocess
from collections import Counter
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

class VisionProcessor:
    """[시니어 최적화] CLIP 모델 및 비전 스캔 파이프라인 분리"""
    def __init__(self, device_detector):
        self.clip_model = None
        self.clip_processor = None
        self.device_detector = device_detector

    def get_clip_model(self, device_mode="auto"):
        """[시니어 최적화] CLIP 모델 Lazy Loading (필요할 때만 로드)"""
        if self.clip_model is None:
            model_name = "openai/clip-vit-base-patch32"
            best_dev = self.device_detector(device_mode)
            self.clip_model = CLIPModel.from_pretrained(model_name).to(best_dev)
            self.clip_processor = CLIPProcessor.from_pretrained(model_name)
        return self.clip_model, self.clip_processor

    def detect_scenes_clip_stream(self, video_path, labels, stop_event, ffmpeg_exe, interval=10, options=None):
        """[시니어 최적화] CLIP 기반 제로샷 영상 분류 및 챕터 생성"""
        options = options or {}
        device_mode = options.get("device_mode", "auto") if isinstance(options, dict) else options.device_mode
        model, processor = self.get_clip_model(device_mode)
        device = self.device_detector(device_mode)
        tmp_dir = tempfile.mkdtemp()
        try:
            cmd = [ffmpeg_exe, '-y', '-i', video_path, '-vf', f'fps=1/{interval}', '-vsync', 'vfr', os.path.join(tmp_dir, 'frame_%04d.jpg')]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            frame_files = sorted(glob.glob(os.path.join(tmp_dir, "*.jpg")))
            total_frames, raw_preds = len(frame_files), []
            for i, img_path in enumerate(frame_files):
                if stop_event.is_set(): break
                inputs = processor(text=labels, images=Image.open(img_path), return_tensors="pt", padding=True).to(device)
                with torch.no_grad(): outputs = model(**inputs)
                raw_preds.append(outputs.logits_per_image.softmax(dim=1).argmax().item())
                del inputs; del outputs
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
        finally: 
            shutil.rmtree(tmp_dir, ignore_errors=True)
            import gc; gc.collect()
            if torch.cuda.is_available(): torch.cuda.empty_cache()
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available(): torch.mps.empty_cache()
