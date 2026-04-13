from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple
import time


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str
    segment_index: int


@dataclass(frozen=True)
class SubtitleRenderStyle:
    font_name: str = "맑은 고딕"
    font_size: int = 80
    fill_color: str = "#FFFFFF"
    outline_width: int = 3
    outline_color: str = "#000000"
    shadow_width: int = 3
    shadow_color: str = "#000000"
    margin_v: int = 50


def build_subtitle_cues(rows: Iterable[dict]) -> List[SubtitleCue]:
    cues: List[SubtitleCue] = []
    for idx, row in enumerate(rows):
        text = str((row or {}).get("t", "") or "").strip()
        if not text:
            continue
        start = float((row or {}).get("s", 0.0) or 0.0)
        end = float((row or {}).get("e", start) or start)
        cues.append(
            SubtitleCue(
                start=max(0.0, start),
                end=max(start, end),
                text=text,
                segment_index=idx,
            )
        )

    normalized: List[SubtitleCue] = []
    for idx, cue in enumerate(cues):
        end = cue.end
        if idx < len(cues) - 1 and end >= cues[idx + 1].start:
            end = round(max(cue.start, cues[idx + 1].start - 0.01), 3)
        normalized.append(
            SubtitleCue(
                start=round(cue.start, 3),
                end=round(end, 3),
                text=cue.text,
                segment_index=cue.segment_index,
            )
        )
    return normalized


def cues_to_entries(cues: Iterable[SubtitleCue]) -> List[dict]:
    return [{"s": cue.start, "e": cue.end, "t": cue.text} for cue in cues]


def remap_cues_for_merged_ranges(cues: Sequence[SubtitleCue], merged_ranges: Sequence[Tuple[float, float]]) -> List[SubtitleCue]:
    remapped: List[SubtitleCue] = []
    current_out = 0.0
    for merged_start, merged_end in merged_ranges:
        for cue in cues:
            if cue.start >= merged_start - 0.001 and cue.end <= merged_end + 0.001:
                remapped.append(
                    SubtitleCue(
                        start=round(current_out + (cue.start - merged_start), 3),
                        end=round(current_out + (cue.end - merged_start), 3),
                        text=cue.text,
                        segment_index=cue.segment_index,
                    )
                )
        current_out += (merged_end - merged_start)
    return remapped


def _fmt_clock(sec: float, millis_sep: str) -> str:
    return time.strftime("%H:%M:%S", time.gmtime(sec)) + f"{millis_sep}{int((sec % 1) * 1000):03d}"


def cues_to_srt(cues: Iterable[SubtitleCue]) -> str:
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(f"{i}\n{_fmt_clock(cue.start, ',')} --> {_fmt_clock(cue.end, ',')}\n{cue.text}\n")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def cues_to_vtt(cues: Iterable[SubtitleCue]) -> str:
    lines = ["WEBVTT", ""]
    for i, cue in enumerate(cues, start=1):
        lines.append(f"{i}")
        lines.append(f"{_fmt_clock(cue.start, '.')} --> {_fmt_clock(cue.end, '.')}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines).rstrip() + ("\n" if len(lines) > 2 else "\n")


def hex_to_rgb_tuple(hex_color: str) -> tuple[int, int, int]:
    color = str(hex_color or "#FFFFFF").lstrip("#")
    if len(color) != 6:
        color = "FFFFFF"
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def ffmpeg_color(hex_color: str) -> str:
    r, g, b = hex_to_rgb_tuple(hex_color)
    return f"0x{r:02X}{g:02X}{b:02X}"


def escape_ffmpeg_value(value: str) -> str:
    value = str(value or "")
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(";", "\\;")
    )
