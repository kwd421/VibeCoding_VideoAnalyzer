import math
from PIL import Image, ImageDraw


def build_overlay_preview_image(self, item, width, height, draft=False):
    width = max(1, int(width))
    height = max(1, int(height))
    if item.type == 'image':
        src = self._get_overlay_source_image(item.source)
        if src is None:
            return None
        resample = Image.BILINEAR if draft else Image.LANCZOS
        img = src.resize((width, height), resample)
        rotation = float(getattr(item, 'rotation', 0.0) or 0.0)
        if abs(rotation) > 0.01:
            img = img.rotate(-rotation, expand=True, resample=Image.BICUBIC if not draft else Image.BILINEAR, fillcolor=(0, 0, 0, 0))
        opacity = max(0.0, min(1.0, float(getattr(item, 'opacity', 1.0) or 1.0)))
        if opacity < 0.999:
            alpha = img.getchannel('A').point(lambda value: int(value * opacity))
            img.putalpha(alpha)
        surface_size = max(int(math.ceil(math.hypot(width, height))), img.width, img.height)
        if img.width != surface_size or img.height != surface_size:
            surface = Image.new('RGBA', (surface_size, surface_size), (0, 0, 0, 0))
            offset_x = (surface_size - img.width) // 2
            offset_y = (surface_size - img.height) // 2
            surface.alpha_composite(img, (offset_x, offset_y))
            img = surface
        return img
    if item.type in ('text', 'subtitle'):
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = self._get_preview_text_font(max(8, int(item.font_size)))
        draw.multiline_text((6, 6), item.text or '', font=font, fill=self._hex_to_rgba(item.text_color, item.opacity), spacing=4)
        return img
    return None


def rotate_overlay_point(self, cx, cy, px, py, rotation_deg):
    theta = math.radians(float(rotation_deg or 0.0))
    dx = px - cx
    dy = py - cy
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    return (
        cx + (dx * cos_t) - (dy * sin_t),
        cy + (dx * sin_t) + (dy * cos_t),
    )


def get_image_overlay_geometry(self, item, preview_w, preview_h):
    x, y, w, h = self.overlay_manager.preview_rect(item, preview_w, preview_h)
    cx = x + (w / 2.0)
    cy = y + (h / 2.0)
    base_corners = [
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h),
    ]
    corners = [self._rotate_overlay_point(cx, cy, px, py, getattr(item, 'rotation', 0.0)) for px, py in base_corners]
    xs = [pt[0] for pt in corners]
    ys = [pt[1] for pt in corners]
    bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return {
        'center': (cx, cy),
        'base_rect': (x, y, w, h),
        'corners': corners,
        'corner_roles': self._get_screen_corner_roles((cx, cy), corners),
        'bbox': bbox,
    }
