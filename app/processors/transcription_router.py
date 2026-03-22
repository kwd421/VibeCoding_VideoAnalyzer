class TranscriptionRouter:
    def __init__(self, faster_whisper_backend, mps_backend=None, coreml_backend=None):
        self.faster_whisper_backend = faster_whisper_backend
        self.mps_backend = mps_backend
        self.coreml_backend = coreml_backend

    def resolve_backend(self, device_mode="auto"):
        if device_mode == "mps" and self.mps_backend and self.mps_backend.is_available():
            return self.mps_backend
        if device_mode == "coreml" and self.coreml_backend and self.coreml_backend.is_available():
            return self.coreml_backend
        return self.faster_whisper_backend

