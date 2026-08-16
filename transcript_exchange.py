"""Machine-readable transcript exchange for VibeCoding_VideoAnalyzer.

This module is intentionally standard-library only. It can be tested without
loading VLC, Torch, Faster-Whisper, or any GUI dependency.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

SCHEMA_ID = "vibe-video-analyzer/transcript"
SCHEMA_VERSION = 1
MAX_SEGMENTS = 100_000
MAX_WORDS = 1_000_000


class TranscriptExchangeError(ValueError):
    """Raised when transcript data cannot be represented safely."""


_MISSING = object()


def _field(value: Any, *names: str, default: Any = _MISSING) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
    else:
        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
    if default is not _MISSING:
        return default
    raise TranscriptExchangeError(f"Missing required field: {' or '.join(names)}")


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TranscriptExchangeError(f"{label} must be a number.")
    result = float(value)
    if not math.isfinite(result):
        raise TranscriptExchangeError(f"{label} must be finite.")
    if result < minimum:
        raise TranscriptExchangeError(f"{label} must be at least {minimum}.")
    return result


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TranscriptExchangeError(f"{label} must be a non-empty string.")
    return value.strip()


def normalize_word(value: Any, *, label: str = "word") -> Dict[str, Any]:
    """Normalize TranscriptWord/dict/object into the exchange word shape."""

    text = _text(_field(value, "text", "word"), f"{label}.text")
    start = _number(_field(value, "startSeconds", "s", "start"), f"{label}.startSeconds")
    end = _number(_field(value, "endSeconds", "e", "end"), f"{label}.endSeconds")
    if end <= start:
        raise TranscriptExchangeError(f"{label}.endSeconds must be greater than startSeconds.")

    normalized: Dict[str, Any] = {
        "text": text,
        "startSeconds": round(start, 6),
        "endSeconds": round(end, 6),
    }
    confidence = _field(value, "confidence", default=None)
    if confidence is not None:
        confidence_value = _number(confidence, f"{label}.confidence")
        if confidence_value > 1:
            raise TranscriptExchangeError(f"{label}.confidence must be between 0 and 1.")
        normalized["confidence"] = round(confidence_value, 6)
    return normalized


def normalize_segment(value: Any, *, index: int) -> Dict[str, Any]:
    """Normalize TranscriptSegment/dict/object into the exchange segment shape."""

    label = f"segments[{index}]"
    start = _number(_field(value, "startSeconds", "s", "start"), f"{label}.startSeconds")
    end = _number(_field(value, "endSeconds", "e", "end"), f"{label}.endSeconds")
    if end <= start:
        raise TranscriptExchangeError(f"{label}.endSeconds must be greater than startSeconds.")
    text = _text(_field(value, "text", "t"), f"{label}.text")

    raw_words = _field(value, "words", default=[]) or []
    if not isinstance(raw_words, (list, tuple)):
        raise TranscriptExchangeError(f"{label}.words must be a list.")

    words: List[Dict[str, Any]] = []
    previous_word_start = -math.inf
    for word_index, raw_word in enumerate(raw_words):
        word = normalize_word(raw_word, label=f"{label}.words[{word_index}]")
        if word["startSeconds"] < previous_word_start:
            raise TranscriptExchangeError(f"{label}.words must be sorted by startSeconds.")
        previous_word_start = word["startSeconds"]
        words.append(word)

    return {
        "id": f"segment-{index + 1}",
        "startSeconds": round(start, 6),
        "endSeconds": round(end, 6),
        "durationSeconds": round(end - start, 6),
        "text": text,
        "words": words,
    }


def normalize_segments(values: Iterable[Any]) -> List[Dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        values = list(values)
    if len(values) > MAX_SEGMENTS:
        raise TranscriptExchangeError(f"Transcript exceeds the {MAX_SEGMENTS}-segment limit.")

    normalized: List[Dict[str, Any]] = []
    previous_start = -math.inf
    total_words = 0
    for index, value in enumerate(values):
        segment = normalize_segment(value, index=index)
        if segment["startSeconds"] < previous_start:
            raise TranscriptExchangeError("Segments must be sorted by startSeconds.")
        previous_start = segment["startSeconds"]
        total_words += len(segment["words"])
        if total_words > MAX_WORDS:
            raise TranscriptExchangeError(f"Transcript exceeds the {MAX_WORDS}-word limit.")
        normalized.append(segment)
    return normalized


def build_transcript_document(
    media_path: str,
    segments: Iterable[Any],
    *,
    duration_seconds: Optional[float] = None,
    engine: Optional[Mapping[str, Any]] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a versioned JSON-compatible transcript document."""

    if not isinstance(media_path, str) or not media_path.strip():
        raise TranscriptExchangeError("media_path must be a non-empty string.")
    resolved_media = str(Path(media_path).expanduser().resolve())
    normalized_segments = normalize_segments(segments)

    if duration_seconds is None:
        duration = normalized_segments[-1]["endSeconds"] if normalized_segments else 0.0
    else:
        duration = _number(duration_seconds, "duration_seconds")

    created = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not isinstance(created, str) or not created.strip():
        raise TranscriptExchangeError("created_at must be a non-empty string.")

    document: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": created,
        "media": {
            "path": resolved_media,
            "fileName": Path(resolved_media).name,
            "durationSeconds": round(duration, 6),
        },
        "segments": normalized_segments,
        "summary": {
            "segmentCount": len(normalized_segments),
            "wordCount": sum(len(segment["words"]) for segment in normalized_segments),
        },
    }
    if engine:
        try:
            json.dumps(engine, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise TranscriptExchangeError(f"engine metadata must be JSON serializable: {exc}") from exc
        document["engine"] = dict(engine)
    return document


def validate_transcript_document(document: Any) -> Dict[str, Any]:
    """Validate and normalize a previously serialized exchange document."""

    if not isinstance(document, Mapping):
        raise TranscriptExchangeError("Transcript document must be an object.")
    if document.get("schema") != SCHEMA_ID:
        raise TranscriptExchangeError(f"Unsupported transcript schema: {document.get('schema')!r}.")
    if document.get("schemaVersion") != SCHEMA_VERSION:
        raise TranscriptExchangeError(
            f"Unsupported transcript schemaVersion: {document.get('schemaVersion')!r}."
        )

    media = document.get("media")
    if not isinstance(media, Mapping):
        raise TranscriptExchangeError("media must be an object.")
    media_path = _text(media.get("path"), "media.path")
    duration = media.get("durationSeconds")
    engine = document.get("engine") if isinstance(document.get("engine"), Mapping) else None
    return build_transcript_document(
        media_path,
        document.get("segments", []),
        duration_seconds=duration,
        engine=engine,
        created_at=_text(document.get("createdAt"), "createdAt"),
    )


def _serialize(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_transcript_json(
    output_path: str,
    document: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> str:
    """Atomically write a transcript JSON document.

    Existing files are preserved unless overwrite=True is explicit.
    """

    normalized = validate_transcript_document(document)
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".json":
        raise TranscriptExchangeError("output_path must end in .json.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialize(normalized)

    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=str(destination.parent),
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        if overwrite:
            os.replace(str(temp_path), str(destination))
            temp_path = None
        else:
            try:
                os.link(str(temp_path), str(destination))
            except FileExistsError as exc:
                raise TranscriptExchangeError(
                    f"Output already exists: {destination}. Use --overwrite to replace it."
                ) from exc
            except OSError:
                try:
                    with destination.open("x", encoding="utf-8", newline="\n") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                except FileExistsError as exc:
                    raise TranscriptExchangeError(
                        f"Output already exists: {destination}. Use --overwrite to replace it."
                    ) from exc
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
                    temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return str(destination)


def load_transcript_json(input_path: str) -> Dict[str, Any]:
    path = Path(input_path).expanduser().resolve()
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError as exc:
        raise TranscriptExchangeError(f"Transcript file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TranscriptExchangeError(f"Invalid transcript JSON at line {exc.lineno}: {exc.msg}") from exc
    return validate_transcript_document(document)
