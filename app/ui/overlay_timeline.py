def refresh_overlay_timeline(self):
    if not hasattr(self, 'overlay_timeline_canvas'):
        return
    canvas = self.overlay_timeline_canvas
    canvas.delete('all')
    self._overlay_timeline_regions = {}
    visible_width = max(400, canvas.winfo_width())
    width = self._get_overlay_timeline_content_width(visible_width)
    row_h = 34
    ruler_h = 24
    top_pad = 10
    total_duration = self._get_overlay_timeline_total_duration()
    track_specs = [(idx, track.name, sorted(track.items, key=lambda ov: (ov.layer_index, ov.id))) for idx, track in enumerate(self.overlay_manager.tracks)]
    subtitle_items = self._get_subtitle_adapter_items()
    if subtitle_items:
        track_specs.append((len(track_specs), '?? ???', subtitle_items))
    self._draw_overlay_timeline_ruler(total_duration, width, ruler_h)
    for track_idx, track_name, track_items in track_specs:
        y1 = top_pad + ruler_h + track_idx * row_h
        y2 = y1 + 24
        canvas.create_text(10, y1 + 12, text=track_name, anchor='w', fill=self.C['text2'], font=('Noto Sans KR', 10))
        for item in track_items:
            x1 = self._time_to_timeline_x(item.start_time, total_duration, width)
            x2 = self._time_to_timeline_x(item.end_time, total_duration, width)
            x2 = max(x1 + 18, x2)
            is_selected = item.id == self.overlay_manager.selected_item_id
            fill = '#0A84FF' if is_selected else ('#5AC8FA' if item.visible else '#8E8E93')
            outline = '#FFFFFF' if is_selected else ''
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=1, tags=(item.id, 'overlay_item'))
            if item.type == 'text':
                tag_name = 'TXT'
            elif item.type == 'subtitle':
                tag_name = 'SUB'
            else:
                tag_name = 'IMG'
            label = f'{tag_name} {item.layer_index}' if item.visible else f'{tag_name} {item.layer_index} OFF'
            text_fill = 'white' if item.visible else '#E5E5EA'
            canvas.create_text(x1 + 6, y1 + 12, text=label, anchor='w', fill=text_fill, font=('Noto Sans KR', 9, 'bold'), tags=(item.id, 'overlay_item'))
            self._overlay_timeline_regions[item.id] = {'rect': (x1, y1, x2, y2), 'track_index': track_idx}
    total_tracks = max(1, len(track_specs))
    scroll_h = 6 if getattr(self, 'overlay_timeline_hscroll', None) and self.overlay_timeline_hscroll.winfo_exists() else 0
    bottom = top_pad + ruler_h + total_tracks * row_h + 12 + scroll_h
    canvas.configure(scrollregion=(0, 0, width, bottom))
    self._update_overlay_timeline_playhead(total_duration, width, row_h, ruler_h, top_pad, total_tracks)


def update_overlay_timeline_playhead(self, total_duration=None, width=None, row_h=34, ruler_h=24, top_pad=10, total_tracks=None):
    if not hasattr(self, 'overlay_timeline_canvas'):
        return
    canvas = self.overlay_timeline_canvas
    if width is None:
        width = self._get_overlay_timeline_content_width()
    if total_duration is None:
        total_duration = 1.0
        if self.player and self.player.get_length() > 0:
            total_duration = max(total_duration, self.player.get_length() / 1000.0)
        for item in self._get_timeline_items():
            total_duration = max(total_duration, item.end_time)
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


def on_overlay_timeline_press(self, event):
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
    min_len = 0.05
    if mode == 'move':
        raw_delta = current_time - drag_state['press_time']
        duration = drag_state['origin_end'] - drag_state['origin_start']
        new_start = self._snap_timeline_time(drag_state['origin_start'] + raw_delta)
        new_end = self._snap_timeline_time(new_start + duration)
        if new_start < 0:
            new_start = 0.0
            new_end = self._snap_timeline_time(new_start + duration)
        self._apply_item_timeline_times(item, new_start, max(new_start + min_len, new_end))
    elif mode == 'trim_start':
        new_start = self._snap_timeline_time(current_time)
        self._apply_item_timeline_times(item, min(max(0.0, new_start), item.end_time - min_len), item.end_time)
    elif mode == 'trim_end':
        new_end = self._snap_timeline_time(current_time)
        self._apply_item_timeline_times(item, item.start_time, max(item.start_time + min_len, new_end))
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
