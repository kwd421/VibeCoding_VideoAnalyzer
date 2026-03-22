import warnings

import torch
from silero_vad import get_speech_timestamps, load_silero_vad


class VADService:
    def __init__(self, device_detector, target_cores_getter):
        self._detect_best_device = device_detector
        self._get_target_cores = target_cores_getter
        self.vad_model = None

    def get_model(self, device_mode="auto"):
        if self.vad_model is None:
            target_threads = self._get_target_cores(device_mode)
            torch.set_num_threads(target_threads)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                self.vad_model = load_silero_vad()

            best_dev = self._detect_best_device(device_mode)
            if best_dev != "cpu":
                self.vad_model = self.vad_model.to(best_dev)

        return self.vad_model

    def get_speech_timestamps(
        self,
        audio_data,
        device_mode="auto",
        vad_threshold=0.35,
        min_silence_ms=2000,
        speech_pad_ms=250,
        sampling_rate=16000,
    ):
        model = self.get_model(device_mode)
        return get_speech_timestamps(
            torch.from_numpy(audio_data),
            model,
            sampling_rate=sampling_rate,
            threshold=vad_threshold,
            min_speech_duration_ms=150,
            min_silence_duration_ms=min_silence_ms,
            speech_pad_ms=speech_pad_ms,
        )

    def detect_speech_stream(self, audio_data, stop_event, min_silence_ms=2000, speech_pad_ms=250, options=None):
        options = options or {}
        if isinstance(options, dict):
            device_mode = options.get("device_mode", "auto")
            vad_threshold = options.get("vad_threshold", 0.35)
        else:
            device_mode = getattr(options, "device_mode", "auto")
            vad_threshold = getattr(options, "vad_threshold", 0.35)

        sample_rate = 16000
        chunk_size = sample_rate * 60
        overlap = sample_rate * 2
        total_samples = len(audio_data)
        last_end_time = 0.0

        for i in range(0, total_samples, chunk_size):
            if stop_event.is_set():
                break
            start = i
            end = min(i + chunk_size + overlap, total_samples)
            timestamps = self.get_speech_timestamps(
                audio_data[start:end],
                device_mode=device_mode,
                vad_threshold=vad_threshold,
                min_silence_ms=min_silence_ms,
                speech_pad_ms=speech_pad_ms,
                sampling_rate=sample_rate,
            )
            offset = start / sample_rate
            chunk_results = []
            for ts in timestamps:
                start_time = offset + ts["start"] / sample_rate
                end_time = offset + ts["end"] / sample_rate
                if end_time <= last_end_time:
                    continue
                start_time = max(start_time, last_end_time)
                if start_time >= end_time:
                    continue
                chunk_results.append({"s": start_time, "e": end_time, "t": f"{end_time - start_time:.2f}s"})
                last_end_time = max(last_end_time, end_time)
            progress = (min(start + chunk_size, total_samples) / total_samples) * 100
            yield chunk_results, progress

