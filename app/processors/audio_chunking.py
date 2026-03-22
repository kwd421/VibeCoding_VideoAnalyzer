import numpy as np


class AudioChunkingService:
    def iter_transcription_chunks(
        self,
        audio_data,
        stop_event,
        sample_rate=16000,
        chunk_seconds=30,
        search_seconds=5,
        energy_window=1600,
    ):
        total_samples = len(audio_data)
        total_duration = total_samples / sample_rate
        chunk_size = sample_rate * chunk_seconds
        search_samples = sample_rate * search_seconds
        start_idx = 0

        while start_idx < total_samples:
            if stop_event.is_set():
                break

            base_end = start_idx + chunk_size
            if base_end >= total_samples:
                end_idx = total_samples
            else:
                search_start = max(start_idx, base_end - search_samples)
                search_chunk = audio_data[search_start:base_end]
                if len(search_chunk) >= energy_window:
                    trimmed = search_chunk[: (len(search_chunk) // energy_window) * energy_window]
                    if len(trimmed) > 0:
                        windows = trimmed.reshape(-1, energy_window)
                        energy = np.sum(windows**2, axis=1)
                        end_idx = search_start + (np.argmin(energy) * energy_window)
                    else:
                        end_idx = base_end
                else:
                    end_idx = base_end

            if end_idx <= start_idx:
                end_idx = min(base_end, total_samples)

            chunk = audio_data[start_idx:end_idx]
            offset_sec = start_idx / sample_rate
            yield chunk, offset_sec, start_idx, end_idx, total_duration
            start_idx = end_idx

