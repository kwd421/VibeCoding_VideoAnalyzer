from faster_whisper import WhisperModel


class FasterWhisperBackend:
    def __init__(self, model_resolver, device_detector, target_cores_getter):
        self._resolve_model_id = model_resolver
        self._detect_best_device = device_detector
        self._get_target_cores = target_cores_getter
        self.model = None
        self.device_mode = "auto"

    def get_model(self, model_id, device_mode="auto"):
        target_threads = self._get_target_cores(device_mode)
        if self.model is None or self.device_mode != device_mode:
            self.device_mode = device_mode
            best_device = self._detect_best_device(device_mode)
            ct2_dev = "cuda" if best_device == "cuda" else "cpu"
            compute_type = "float16" if ct2_dev == "cuda" else "int8"
            workers = 2 if ct2_dev == "cpu" else 1
            threads_per_worker = max(1, target_threads // workers)
            model_source = self._resolve_model_id(model_id)
            self.model = WhisperModel(
                model_source,
                device=ct2_dev,
                compute_type=compute_type,
                cpu_threads=threads_per_worker,
                num_workers=workers,
            )
        return self.model

