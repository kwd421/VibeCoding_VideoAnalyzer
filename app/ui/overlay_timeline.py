import io
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageTk


HANDLE_FILL = '#233B4D'
HANDLE_OUTLINE = '#172733'
HANDLE_FILL_SELECTED = '#2E5266'
HANDLE_OUTLINE_SELECTED = '#FFFFFF'
DIVIDER_NORMAL = '#172733'
DIVIDER_SELECTED = '#FFFFFF'
GRIP_NORMAL = '#DCE7EF'
GRIP_SELECTED = '#F7FBFF'
PREVIEW_BG = '#101821'
PREVIEW_TEXT = '#F3F6FA'
PREVIEW_TEXT_MUTED = '#D7DEE6'
TRACK_ROW_HEIGHT = 68
BLOCK_HEIGHT = 52
LABEL_HEIGHT = 16
THUMB_CORNER_PAD = 4
MIN_BLOCK_WIDTH = 28
MIN_TRIM_SECONDS = 0.1
THUMB_CACHE_LIMIT = 96
SHOW_TIMELINE_THUMBS = False


def _ensure_timeline_preview_state(self):
    if not hasattr(self, '_overlay_timeline_photo_refs'):
        self._overlay_timeline_photo_refs = {}
    if not hasattr(self, '_overlay_timeline_thumb_cache'):
        self._overlay_timeline_thumb_cache = {}
    self._overlay_timeline_photo_refs = {}


def _cache_timeline_thumb(self, key, image):
    cache = self._overlay_timeline_thumb_cache
    cache[key] = image
    if len(cache) > THUMB_CACHE_LIMIT:
        oldest_key = next(iter(cache))
        if oldest_key != key:
            cache.pop(oldest_key, None)


def _compose_thumb_surface(image, width, height, background=PREVIEW_BG):
    surface = Image.new('RGBA', (width, height), background)
    if image is not None:
        img = image.copy().convert('RGBA')
        img.thumbnail((max(1, width - 4), max(1, height - 4)), Image.LANCZOS)
        px = int(round((width - img.width) / 2.0))
        py = int(round((height - img.height) / 2.0))
        surface.alpha_composite(img, (px, py))
    return surface


def _get_image_timeline_thumb(self, item, width, height):
    source = getattr(item, 'source', None)
    if not source or not os.path.exists(source):
        return None
    key = ('image', source, int(width), int(height))
    cached = self._overlay_timeline_thumb_cache.get(key)
    if cached is not None:
        return cached
    try:
        img = Image.open(source).convert('RGBA')
        surface = _compose_thumb_surface(img, width, height)
        _cache_timeline_thumb(self, key, surface)
        return surface
    except Exception:
        return None


def _get_text_timeline_thumb(self, item, width, height):
    text_value = (item.text or '텍스트').strip() or '텍스트'
    key = ('text', text_value, int(width), int(height))
    cached = self._overlay_timeline_thumb_cache.get(key)
    if cached is not None:
        return cached
    surface = Image.new('RGBA', (width, height), PREVIEW_BG)
    draw = ImageDraw.Draw(surface)
    font = ImageFont.load_default()
    preview = text_value[:20]
    bbox = draw.textbbox((0, 0), preview, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((max(4, int((width - tw) / 2)), max(2, int((height - th) / 2))), preview, fill=PREVIEW_TEXT, font=font)
    _cache_timeline_thumb(self, key, surface)
    return surface


def _get_audio_timeline_thumb(self, item, width, height):
    key = ('audio', int(width), int(height))
    cached = self._overlay_timeline_thumb_cache.get(key)
    if cached is not None:
        return cached
    surface = Image.new('RGBA', (width, height), PREVIEW_BG)
    draw = ImageDraw.Draw(surface)
    bars = [0.3, 0.65, 0.9, 0.55, 0.75, 0.4]
    step = max(3, int(width / (len(bars) + 2)))
    x = max(4, int((width - (len(bars) - 1) * step) / 2))
    center_y = height / 2.0
    for scale in bars:
        bar_h = max(4, int((height - 6) * scale))
        y1 = int(center_y - bar_h / 2.0)
        y2 = int(center_y + bar_h / 2.0)
        draw.rounded_rectangle((x, y1, x + 3, y2), radius=1, fill=PREVIEW_TEXT_MUTED)
        x += step
    _cache_timeline_thumb(self, key, surface)
    return surface


def _get_video_timeline_thumb(self, item, local_time_sec, width, height):
    ffmpeg_path = getattr(getattr(self, 'video_editor', None), 'ffmpeg_path', None)
    source = getattr(item, 'source', None)
    if not ffmpeg_path or not source or not os.path.exists(source):
        return None
    bucket = round(float(local_time_sec), 1)
    key = ('video', source, bucket, int(width), int(height))
    cached = self._overlay_timeline_thumb_cache.get(key)
    if cached is not None:
        return cached
    cmd = [
        ffmpeg_path,
        '-ss',
        f'{max(0.0, bucket):.3f}',
        '-i',
        source,
        '-frames:v',
        '1',
        '-vf',
        f'scale={max(1, int(width))}:{max(1, int(height))}:force_original_aspect_ratio=decrease',
        '-f',
        'image2pipe',
        '-vcodec',
        'png',
        '-',
    ]
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, check=False)
        if proc.returncode != 0 or not proc.stdout:
            return None
        img = Image.open(io.BytesIO(proc.stdout)).convert('RGBA')
        surface = _compose_thumb_surface(img, width, height)
        _cache_timeline_thumb(self, key, surface)
        return surface
    except Exception:
        return None


def _draw_timeline_thumb(self, canvas, item_id, image, x, y):
    photo = ImageTk.PhotoImage(image)
    self._overlay_timeline_photo_refs[f'{item_id}:{x}:{y}:{len(self._overlay_timeline_photo_refs)}'] = photo
    canvas.create_image(x, y, image=photo, anchor='nw', tags=(item_id, 'overlay_item', 'overlay_preview_thumb'))


def _draw_item_preview(self, canvas, item, x1, y1, x2, y2, handle_w, is_selected):
    if not SHOW_TIMELINE_THUMBS:
        return
    body_x1 = int(round(x1 + handle_w + 2))
    body_x2 = int(round(x2 - handle_w - 2))
    preview_y1 = int(round(y1 + THUMB_CORNER_PAD))
    preview_y2 = int(round(y2 - LABEL_HEIGHT - 2))
    preview_h = preview_y2 - preview_y1
    preview_w = body_x2 - body_x1
    if preview_w < 18 or preview_h < 12:
        return
    if item.type == 'image':
        thumb = _get_image_timeline_thumb(self, item, preview_w, preview_h)
        if thumb is not None:
            _draw_timeline_thumb(self, canvas, item.id, thumb, body_x1, preview_y1)
    elif item.type == 'text':
        thumb = _get_text_timeline_thumb(self, item, preview_w, preview_h)
        if thumb is not None:
            _draw_timeline_thumb(self, canvas, item.id, thumb, body_x1, preview_y1)
    elif item.type == 'audio':
        thumb = _get_audio_timeline_thumb(self, item, preview_w, preview_h)
        if thumb is not None:
            _draw_timeline_thumb(self, canvas, item.id, thumb, body_x1, preview_y1)
    elif item.type == 'video':
        duration = max(0.1, float(item.end_time - item.start_time))
        slot_w = max(26, min(56, preview_h * 16 // 9 if preview_h > 0 else 36))
        max_slots = max(1, int(preview_w // max(slot_w + 4, 1)))
        step = max(1.0, duration / max_slots)
        offset = 0.0
        last_draw_x = None
        while offset < duration + 0.001:
            local_time = min(duration, offset)
            thumb = _get_video_timeline_thumb(self, item, local_time, slot_w, preview_h)
            if thumb is not None:
                px = int(round(self._time_to_timeline_x(item.start_time + local_time, self._get_overlay_timeline_total_duration(), self._get_overlay_timeline_content_width(max(400, canvas.winfo_width()))) - slot_w / 2.0))
                px = max(body_x1, min(body_x2 - slot_w, px))
                if last_draw_x is None or abs(px - last_draw_x) >= slot_w - 4:
                    _draw_timeline_thumb(self, canvas, item.id, thumb, px, preview_y1)
                    last_draw_x = px
            offset += step


def _draw_trim_time_badge(self, canvas, x_center, y_bottom, text, align='center'):
    text_id = canvas.create_text(x_center, y_bottom, text=text, anchor='s', fill='white', font=('Noto Sans KR', 9, 'bold'), tags=('trim_time_badge',))
    x1, y1, x2, y2 = canvas.bbox(text_id)
    pad_x = 6
    pad_y = 3
    if align == 'left':
        dx = max(0, 18 - x1)
        if dx:
            canvas.move(text_id, dx, 0)
            x1, y1, x2, y2 = canvas.bbox(text_id)
    elif align == 'right':
        max_x = canvas.winfo_width() - 18
        dx = min(0, max_x - x2)
        if dx:
            canvas.move(text_id, dx, 0)
            x1, y1, x2, y2 = canvas.bbox(text_id)
    rect_id = canvas.create_rectangle(x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y, fill='#16222C', outline='#4F6B7D', width=1, tags=('trim_time_badge',))
    canvas.tag_raise(text_id, rect_id)


def refresh_overlay_timeline(self):
    if not hasattr(self, 'overlay_timeline_canvas'):
        return
    canvas = self.overlay_timeline_canvas
    try:
        canvas.update_idletasks()
    except Exception:
        pass
    canvas.delete('all')
    _ensure_timeline_preview_state(self)
    self._overlay_timeline_regions = {}
    visible_width = max(400, canvas.winfo_width())
    width = self._get_overlay_timeline_content_width(visible_width)
    row_h = TRACK_ROW_HEIGHT
    ruler_h = 24
    top_pad = 16
    total_duration = self._get_overlay_timeline_total_duration()
    track_specs = [(idx, track.name, sorted(track.items, key=lambda ov: (ov.layer_index, ov.id))) for idx, track in enumerate(self.overlay_manager.tracks)]
    subtitle_items = self._get_subtitle_adapter_items()
    if subtitle_items:
        track_specs.append((len(track_specs), '자막 어댑터', subtitle_items))
    self._draw_overlay_timeline_ruler(total_duration, width, ruler_h)
    for track_idx, track_name, track_items in track_specs:
        y1 = top_pad + ruler_h + track_idx * row_h
        y2 = y1 + BLOCK_HEIGHT
        canvas.create_text(10, y1 + int(BLOCK_HEIGHT / 2), text=track_name, anchor='w', fill=self.C['text2'], font=('Noto Sans KR', 10))
        for item in track_items:
            x1 = self._time_to_timeline_x(item.start_time, total_duration, width)
            x2 = self._time_to_timeline_x(item.end_time, total_duration, width)
            x2 = max(x1 + MIN_BLOCK_WIDTH, x2)
            is_selected = item.id == self.overlay_manager.selected_item_id
            style_map = {
                'video': ('VID', '#34C759'),
                'image': ('IMG', '#5AC8FA'),
                'text': ('TXT', '#0A84FF'),
                'audio': ('AUD', '#FF9F0A'),
                'subtitle': ('SUB', '#AF52DE'),
            }
            tag_name, base_fill = style_map.get(item.type, ('ITM', '#8E8E93'))
            fill = '#0A84FF' if is_selected else (base_fill if item.visible else '#8E8E93')
            outline = '#FFFFFF' if is_selected else '#4A4A4F'
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2 if is_selected else 1, tags=(item.id, 'overlay_item'))

            handle_w = min(12, max(8, int((x2 - x1) / 6)))
            handle_fill = HANDLE_FILL_SELECTED if is_selected else HANDLE_FILL
            handle_outline = HANDLE_OUTLINE_SELECTED if is_selected else HANDLE_OUTLINE
            left_x2 = min(x2, x1 + handle_w)
            right_x1 = max(x1, x2 - handle_w)
            canvas.create_rectangle(x1, y1, left_x2, y2, fill=handle_fill, outline=handle_outline, width=1, tags=(item.id, 'overlay_item', 'trim_left_handle'))
            canvas.create_rectangle(right_x1, y1, x2, y2, fill=handle_fill, outline=handle_outline, width=1, tags=(item.id, 'overlay_item', 'trim_right_handle'))
            divider_color = DIVIDER_SELECTED if is_selected else DIVIDER_NORMAL
            canvas.create_line(left_x2, y1 + 2, left_x2, y2 - 2, fill=divider_color, width=1, tags=(item.id, 'overlay_item'))
            canvas.create_line(right_x1, y1 + 2, right_x1, y2 - 2, fill=divider_color, width=1, tags=(item.id, 'overlay_item'))
            grip_color = GRIP_SELECTED if is_selected else GRIP_NORMAL
            left_mid = x1 + handle_w / 2.0
            right_mid = x2 - handle_w / 2.0
            for grip_x in (left_mid, right_mid):
                canvas.create_line(grip_x - 1, y1 + 9, grip_x - 1, y2 - 9, fill=grip_color, width=1, tags=(item.id, 'overlay_item'))
                canvas.create_line(grip_x + 1, y1 + 9, grip_x + 1, y2 - 9, fill=grip_color, width=1, tags=(item.id, 'overlay_item'))

            _draw_item_preview(self, canvas, item, x1, y1, x2, y2, handle_w, is_selected)

            label_text = (item.text or item.source or '').strip() if item.type in ('audio', 'video') else ''
            if item.type == 'text' and item.text:
                label = f'{tag_name} {item.text[:18]}'
            elif item.type == 'image':
                label = f'{tag_name} 이미지'
            elif label_text:
                label = f'{tag_name} {os.path.basename(label_text)}'
            else:
                label = f'{tag_name} {item.layer_index}' if item.visible else f'{tag_name} {item.layer_index} OFF'
            text_fill = 'white' if item.visible else '#E5E5EA'
            canvas.create_text(x1 + handle_w + 6, y2 - 8, text=label, anchor='w', fill=text_fill, font=('Noto Sans KR', 9, 'bold'), tags=(item.id, 'overlay_item'))

            if is_selected:
                _draw_trim_time_badge(self, canvas, x1 + handle_w / 2.0, y1 - 4, self.format_time(item.start_time), align='left')
                _draw_trim_time_badge(self, canvas, x2 - handle_w / 2.0, y1 - 4, self.format_time(item.end_time), align='right')

            self._overlay_timeline_regions[item.id] = {
                'rect': (x1, y1, x2, y2),
                'track_index': track_idx,
                'handle_w': handle_w,
            }
    total_tracks = max(1, len(track_specs))
    scroll_h = 6 if getattr(self, 'overlay_timeline_hscroll', None) and self.overlay_timeline_hscroll.winfo_exists() else 0
    bottom = top_pad + ruler_h + total_tracks * row_h + 16 + scroll_h
    canvas.configure(scrollregion=(0, 0, width, bottom))
    self._update_overlay_timeline_playhead(total_duration, width, row_h, ruler_h, top_pad, total_tracks)


def update_overlay_timeline_playhead(self, total_duration=None, width=None, row_h=TRACK_ROW_HEIGHT, ruler_h=24, top_pad=16, total_tracks=None):
    if not hasattr(self, 'overlay_timeline_canvas'):
        return
    canvas = self.overlay_timeline_canvas
    if width is None:
        width = self._get_overlay_timeline_content_width()
    if total_duration is None:
        total_duration = self._get_overlay_timeline_total_duration()
    if total_tracks is None:
        total_tracks = max(1, len(self.overlay_manager.tracks) + (1 if self._get_subtitle_adapter_items() else 0))
    current_sec = self._get_overlay_time()
    x = self._time_to_timeline_x(current_sec, total_duration, width)
    y1 = 4
    y2 = top_pad + ruler_h + total_tracks * row_h + 6
    if self._overlay_timeline_playhead and canvas.type(self._overlay_timeline_playhead):
        canvas.coords(self._overlay_timeline_playhead, x, y1, x, y2)
        canvas.itemconfigure(self._overlay_timeline_playhead, fill='#FF453A', width=2)
    else:
        self._overlay_timeline_playhead = canvas.create_line(x, y1, x, y2, fill='#FF453A', width=2)
    try:
        canvas_width = max(1, canvas.winfo_width())
        view_left = canvas.canvasx(0)
        view_right = canvas.canvasx(canvas_width)
        margin = max(48.0, canvas_width * 0.12)
        target_left = None
        if x > (view_right - margin):
            target_left = x - (canvas_width - margin)
        elif x < (view_left + margin):
            target_left = x - margin
        if target_left is not None:
            scrollregion = canvas.cget('scrollregion')
            if scrollregion:
                parts = [float(v) for v in str(scrollregion).split()]
                if len(parts) == 4:
                    region_left, _, region_right, _ = parts
                    total_span = max(1.0, region_right - region_left)
                    max_left = max(region_left, region_right - canvas_width)
                    target_left = min(max(region_left, target_left), max_left)
                    fraction = 0.0 if total_span <= canvas_width else (target_left - region_left) / (total_span - canvas_width)
                    canvas.xview_moveto(min(1.0, max(0.0, fraction)))
    except Exception:
        pass


def on_overlay_timeline_press(self, event):
    try:
        self.overlay_timeline_canvas.focus_set()
    except Exception:
        pass
    canvas_x = self.overlay_timeline_canvas.canvasx(event.x)
    shift_pressed = bool(event.state & 0x0001)
    hits = self._hit_overlay_timeline_items(canvas_x, event.y)
    item_id, mode = self._pick_overlay_timeline_hit(hits, canvas_x, event.y, advance=shift_pressed or len(hits) > 1)
    if not item_id:
        self._overlay_timeline_drag = {'item_id': None, 'mode': None, 'press_time': 0.0, 'origin_start': 0.0, 'origin_end': 0.0}
        self._clear_selected_overlay(refresh_preview=True, refresh_timeline=True)
        return
    item = self._get_any_overlay_item(item_id)
    if item is None:
        self._overlay_timeline_drag = {'item_id': None, 'mode': None, 'press_time': 0.0, 'origin_start': 0.0, 'origin_end': 0.0}
        return
    press_time = self._timeline_x_to_time(canvas_x)
    self._overlay_timeline_drag = {
        'item_id': item_id,
        'mode': mode,
        'press_time': press_time,
        'origin_start': item.start_time,
        'origin_end': item.end_time,
    }
    self._set_selected_overlay(item_id, refresh_preview=True, refresh_timeline=True)


def on_overlay_timeline_drag(self, event):
    drag_state = getattr(self, '_overlay_timeline_drag', None)
    if not drag_state:
        return
    item_id = drag_state.get('item_id')
    if not item_id:
        return
    item = self._get_any_overlay_item(item_id)
    if item is None:
        return
    mode = drag_state.get('mode')
    current_time = self._timeline_x_to_time(self.overlay_timeline_canvas.canvasx(event.x))
    if mode == 'move':
        raw_delta = current_time - drag_state['press_time']
        duration = drag_state['origin_end'] - drag_state['origin_start']
        new_start = self._snap_timeline_time(drag_state['origin_start'] + raw_delta)
        new_end = self._snap_timeline_time(new_start + duration)
        if new_start < 0:
            new_start = 0.0
            new_end = self._snap_timeline_time(new_start + duration)
        self._apply_item_timeline_times(item, new_start, max(new_start + MIN_TRIM_SECONDS, new_end))
    elif mode == 'trim_left':
        new_start = self._snap_timeline_time(current_time)
        self._apply_item_timeline_times(item, min(max(0.0, new_start), item.end_time - MIN_TRIM_SECONDS), item.end_time)
    elif mode == 'trim_right':
        new_end = self._snap_timeline_time(current_time)
        self._apply_item_timeline_times(item, item.start_time, max(item.start_time + MIN_TRIM_SECONDS, new_end))
    self.refresh_overlay_preview()
    self.refresh_overlay_timeline()
    self.refresh_overlay_property_panel()


def on_overlay_timeline_release(self, event):
    drag_state = getattr(self, '_overlay_timeline_drag', None)
    if drag_state and drag_state.get('item_id'):
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()
    self._overlay_timeline_drag = {'item_id': None, 'mode': None, 'press_time': 0.0, 'origin_start': 0.0, 'origin_end': 0.0}
