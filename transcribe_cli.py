#!/usr/bin/env python3
"""Headless transcript exporter for VibeCoding_VideoAnalyzer.

Heavy project dependencies are imported only after argument parsing, so
`python transcribe_cli.py --help` works even before the runtime is restored.
"""

from __future__ import annotations

import argparse
import gc
import sys
import threading
from pathlib import Path
from typing import Any, Iterable, List

from transcript_exchange import (
    TranscriptExchangeError,
    build_transcript_document,
    write_transcript_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Transcribe a local video/audio file with the existing Vibe analyzer "
            "engine and preserve segment/word timestamps in versioned JSON."
        )
    )
    parser.add_argument("input", help="Local video or audio path.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path. Defaults to <input>.vibe-transcript.json.",
    )
    parser.add_argument("--language", default="ko", help="Whisper language code or auto.")
    parser.add_argument("--device", default="auto", help="Existing engine device mode.")
    parser.add_argument("--model", default="large-v3-turbo", help="Model id or local model directory.")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--min-silence-ms", type=int, default=2000)
    parser.add_argument("--speech-pad-ms", type=int, default=250)
    parser.add_argument("--vad-threshold", type=float, default=0.35)
    parser.add_argument("--denoise", action="store_true")
    parser.add_argument("--dominant-speaker", action="store_true")
    parser.add_argument("--whisper-vad", action="store_true")
    parser.add_argument("--silero-vad", action="store_true")
    parser.add_argument("--whisperx-align", action="store_true")
    parser.add_argument("--remove-punctuation", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.vibe-transcript.json")


def _collect_segments(generator: Iterable[Any]) -> List[Any]:
    segments: List[Any] = []
    for item in generator:
        if isinstance(item, dict) and item.get("is_heartbeat"):
            progress = item.get("progress")
            if isinstance(progress, (int, float)):
                print(f"[transcribe] {progress:5.1f}%", file=sys.stderr)
            continue
        segments.append(item)
    return segments


def run(args: argparse.Namespace) -> str:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise TranscriptExchangeError(f"Input media does not exist: {input_path}")
    output_path = Path(args.output).expanduser().resolve() if args.output else _default_output_path(input_path)

    # Keep heavy dependencies out of import-time paths and pure exchange tests.
    try:
        from config_models import AnalysisSettings
        from engine_core import HAS_WHISPERX, HyperTranscriptionEngine
    except ImportError as exc:
        raise RuntimeError(
            "Vibe analyzer runtime dependencies are missing. Restore the project virtual "
            "environment and install VLC/Python media and model packages before transcribing. "
            f"Original import error: {exc}"
        ) from exc

    if args.whisperx_align and not HAS_WHISPERX:
        raise RuntimeError("--whisperx-align was requested, but whisperx is not installed.")
    if args.beam_size < 1:
        raise TranscriptExchangeError("--beam-size must be at least 1.")
    if args.min_silence_ms < 0 or args.speech_pad_ms < 0:
        raise TranscriptExchangeError("Silence and pad values must be non-negative.")
    if not 0.0 < args.vad_threshold < 1.0:
        raise TranscriptExchangeError("--vad-threshold must be between 0 and 1.")

    engine = HyperTranscriptionEngine()
    engine.set_model_id(args.model)
    audio_data = None
    try:
        print(f"[transcribe] loading audio: {input_path}", file=sys.stderr)
        audio_data, media_duration = engine.load_audio_to_memory(str(input_path))
        settings = AnalysisSettings(
            device_mode=args.device,
            beam_size=args.beam_size,
            use_denoise=args.denoise,
            use_dominant=args.dominant_speaker,
            language=args.language,
            vad_threshold=args.vad_threshold,
            min_silence_ms=args.min_silence_ms,
            speech_pad_ms=args.speech_pad_ms,
            use_word_timestamps=True,
            use_whisper_vad=args.whisper_vad,
            use_silero_vad=args.silero_vad,
            use_whisperx_align=args.whisperx_align,
            remove_punctuation=args.remove_punctuation,
        )
        generator, reported_duration = engine.transcribe_stream_raw(
            audio_data,
            threading.Event(),
            settings,
        )
        segments = _collect_segments(generator)
        duration = reported_duration if reported_duration is not None else media_duration
        document = build_transcript_document(
            str(input_path),
            segments,
            duration_seconds=duration,
            engine={
                "application": "VibeCoding_VideoAnalyzer",
                "modelId": args.model,
                "language": args.language,
                "deviceMode": args.device,
                "wordTimestamps": True,
                "whisperXAlign": bool(args.whisperx_align),
                "sileroVad": bool(args.silero_vad),
                "whisperVad": bool(args.whisper_vad),
                "denoise": bool(args.denoise),
            },
        )
        return write_transcript_json(
            str(output_path),
            document,
            overwrite=bool(args.overwrite),
        )
    finally:
        if audio_data is not None:
            del audio_data
        gc.collect()


def main(argv: Any = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output_path = run(args)
    except (TranscriptExchangeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: transcription interrupted", file=sys.stderr)
        return 130
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
