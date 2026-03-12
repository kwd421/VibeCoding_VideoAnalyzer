from __future__ import annotations

from typing import Dict, Iterable, List

from overlay_manager import OverlayItem


def _coerce_get(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_subtitle_overlays(
    rows: Iterable,
    render_width: int,
    render_height: int,
    font_size: float = 80.0,
    text_color: str = '#FFFFFF',
    margin_v: int = 50,
    opacity: float = 1.0,
    track_index: int = 1,
    overrides: Dict[int, Dict[str, object]] | None = None,
) -> List[OverlayItem]:
    render_width = max(1, int(render_width))
    render_height = max(1, int(render_height))
    margin_v = max(0, int(margin_v))
    box_width = max(120.0, float(render_width - 160))
    box_height = max(72.0, float(font_size * 2.2))
    x = max(0.0, (render_width - box_width) / 2.0)
    y = max(0.0, render_height - margin_v - box_height)

    overrides = overrides or {}
    overlays: List[OverlayItem] = []
    for idx, row in enumerate(rows):
        text_value = str(_coerce_get(row, 't', '') or '').strip()
        if not text_value:
            continue
        start_time = float(_coerce_get(row, 's', 0.0) or 0.0)
        end_time = max(start_time, float(_coerce_get(row, 'e', start_time) or start_time))
        ov_override = overrides.get(idx, {})
        ov_start_time = max(0.0, float(ov_override.get('start_time', start_time)))
        ov_end_time = max(ov_start_time, float(ov_override.get('end_time', end_time)))
        ov_x = max(0.0, float(ov_override.get('x', x)))
        ov_y = max(0.0, float(ov_override.get('y', y)))
        ov_font_size = max(8.0, float(ov_override.get('font_size', font_size)))
        ov_color = str(ov_override.get('text_color', text_color) or text_color)
        ov_visible = bool(ov_override.get('visible', True))
        overlays.append(
            OverlayItem(
                id=f"subtitle-adapter-{idx}",
                type="subtitle",
                text=text_value,
                start_time=ov_start_time,
                end_time=ov_end_time,
                track_index=track_index,
                layer_index=idx,
                x=ov_x,
                y=ov_y,
                width=box_width,
                height=max(72.0, float(ov_font_size * 2.2)),
                opacity=opacity,
                visible=ov_visible,
                font_size=ov_font_size,
                text_color=ov_color,
                text_align='center',
                extra={'segment_index': idx, 'adapter': 'subtitle'},
            )
        )
    return overlays
