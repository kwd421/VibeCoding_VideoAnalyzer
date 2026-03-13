from __future__ import annotations

import os
from typing import Callable, List, Tuple
from PIL import Image, ImageDraw, ImageFont


def clamp_hex_color(color: str | None, default: str = '#FFFFFF') -> str:
    color = (color or default).strip()
    if not color.startswith('#'):
        return default
    if len(color) == 4:
        return '#' + ''.join(ch * 2 for ch in color[1:])
    if len(color) != 7:
        return default
    try:
        int(color[1:], 16)
    except Exception:
        return default
    return color.upper()


def hex_to_rgba(color: str | None, opacity: float = 1.0) -> Tuple[int, int, int, int]:
    color = clamp_hex_color(color)
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    a = int(max(0.0, min(1.0, opacity)) * 255)
    return r, g, b, a


def get_text_font(size: int):
    for name in ['malgun.ttf', 'arial.ttf', 'segoeui.ttf']:
        path = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap_text_lines(text: str, max_width: int, measure: Callable[[str], int]) -> List[str]:
    max_width = max(1, int(max_width))
    paragraphs = (text or '').splitlines() or ['']
    lines: List[str] = []
    for para in paragraphs:
        if not para:
            lines.append('')
            continue
        current = ''
        for ch in para:
            candidate = current + ch
            if current and measure(candidate) > max_width:
                lines.append(current)
                current = ch
            else:
                current = candidate
        lines.append(current)
    return lines or ['']


def render_text_overlay_image(
    text: str,
    width: int,
    height: int,
    font_size: float,
    text_color: str,
    opacity: float,
    text_align: str = 'left',
    padding: int = 6,
    line_spacing: int = 4,
):
    width = max(1, int(width))
    height = max(1, int(height))
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_text_font(max(8, int(font_size)))
    fill = hex_to_rgba(text_color, opacity)
    usable_width = max(1, width - (padding * 2))

    def measure(value: str) -> int:
        if not value:
            return 0
        bbox = draw.textbbox((0, 0), value, font=font)
        return max(0, bbox[2] - bbox[0])

    lines = wrap_text_lines(text or '', usable_width, measure)
    probe_bbox = draw.textbbox((0, 0), 'Ag', font=font)
    line_height = max(1, probe_bbox[3] - probe_bbox[1])
    y = padding
    for line in lines:
        line_width = measure(line)
        if text_align == 'center':
            x = max(padding, int((width - line_width) / 2))
        else:
            x = padding
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height + line_spacing
        if y > height:
            break
    return img, lines
