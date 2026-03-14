import os
from tkinter import messagebox


def refresh_overlay_property_panel(self):
    if getattr(self, 'lbl_overlay_props', None) is None:
        return
    selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
    if selected is None:
        for key, var in self.overlay_prop_vars.items():
            if key == 'visible':
                var.set(False)
            else:
                var.set('')
        self.lbl_overlay_props.config(text='선택된 오버레이가 없습니다')
        for ent in self.overlay_prop_entries.values():
            ent.configure(state='disabled')
        for btn in [self.btn_apply_overlay_props, self.btn_overlay_forward, self.btn_overlay_backward, self.btn_overlay_front, self.btn_overlay_back, self.overlay_visible_check]:
            btn.configure(state='disabled')
        return
    values = {
        'text': selected.text or '',
        'x': self._fmt_overlay_prop(selected.x, 0),
        'y': self._fmt_overlay_prop(selected.y, 0),
        'width': self._fmt_overlay_prop(selected.width, 0),
        'height': self._fmt_overlay_prop(selected.height, 0),
        'start_time': self._fmt_overlay_prop(selected.start_time, 2),
        'end_time': self._fmt_overlay_prop(selected.end_time, 2),
        'opacity': self._fmt_overlay_prop(selected.opacity, 2),
        'font_size': self._fmt_overlay_prop(selected.font_size, 0),
        'text_color': selected.text_color or '#FFFFFF',
        'rotation': self._fmt_overlay_prop(selected.rotation, 1),
    }
    for key, value in values.items():
        self.overlay_prop_vars[key].set(value)
    self.overlay_prop_vars['visible'].set(bool(selected.visible))
    vis_text = '표시' if selected.visible else '숨김'
    name = selected.text if selected.type == 'text' else os.path.basename(selected.source or selected.id)
    self.lbl_overlay_props.config(text=f'이름: {name}\n유형: {selected.type}\n레이어: {selected.layer_index}\n상태: {vis_text}')
    for key, ent in self.overlay_prop_entries.items():
        if key in ('text', 'font_size', 'text_color') and selected.type != 'text':
            ent.configure(state='disabled')
        elif key == 'rotation' and selected.type != 'image':
            ent.configure(state='disabled')
        else:
            ent.configure(state='normal')
    for btn in [self.btn_apply_overlay_props, self.btn_overlay_forward, self.btn_overlay_backward, self.btn_overlay_front, self.btn_overlay_back, self.overlay_visible_check]:
        btn.configure(state='normal')


def apply_selected_overlay_properties(self):
    selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
    if selected is None:
        return
    try:
        if selected.type != 'subtitle':
            selected.x = max(0.0, float(self.overlay_prop_vars['x'].get()))
        if selected.type != 'subtitle':
            selected.y = max(0.0, float(self.overlay_prop_vars['y'].get()))
            selected.width = max(16.0, float(self.overlay_prop_vars['width'].get()))
            selected.height = max(16.0, float(self.overlay_prop_vars['height'].get()))
            if selected.type == 'image':
                selected.rotation = float(self.overlay_prop_vars['rotation'].get() or selected.rotation or 0.0)
        start_time = max(0.0, float(self.overlay_prop_vars['start_time'].get()))
        end_time = max(start_time, float(self.overlay_prop_vars['end_time'].get()))
        if selected.type == 'subtitle':
            idx = self._get_subtitle_segment_index(selected)
            if idx is None:
                return
            ov = dict(self.subtitle_adapter_overrides.get(idx, {}))
            ov['start_time'] = start_time
            ov['end_time'] = end_time
            ov['visible'] = bool(self.overlay_prop_vars['visible'].get())
            ov['font_size'] = max(8.0, float(self.overlay_prop_vars['font_size'].get() or selected.font_size or 48))
            color = self.overlay_prop_vars['text_color'].get().strip() or '#FFFFFF'
            if not color.startswith('#') or len(color) not in (4, 7):
                raise ValueError
            ov['text_color'] = color
            self.subtitle_adapter_overrides[idx] = ov
        else:
            selected.start_time = start_time
            selected.end_time = end_time
            selected.opacity = max(0.0, min(1.0, float(self.overlay_prop_vars['opacity'].get())))
            selected.visible = bool(self.overlay_prop_vars['visible'].get())
        if selected.type == 'text':
            selected.text = self.overlay_prop_vars['text'].get()
            selected.font_size = max(8.0, float(self.overlay_prop_vars['font_size'].get() or 48))
            color = self.overlay_prop_vars['text_color'].get().strip() or '#FFFFFF'
            if not color.startswith('#') or len(color) not in (4, 7):
                raise ValueError
            selected.text_color = color
    except ValueError:
        messagebox.showerror('오류', '오버레이 속성 값을 다시 확인해 주세요.')
        return
    self._invalidate_overlay_preview_cache(selected.id)
    self.refresh_overlay_preview()
    self.refresh_overlay_timeline()
    self.refresh_overlay_property_panel()


def on_toggle_selected_overlay_visible(self):
    selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
    if selected is None:
        return
    if selected.type == 'subtitle':
        idx = self._get_subtitle_segment_index(selected)
        if idx is None:
            return
        ov = dict(self.subtitle_adapter_overrides.get(idx, {}))
        ov['visible'] = bool(self.overlay_prop_vars['visible'].get())
        self.subtitle_adapter_overrides[idx] = ov
    else:
        selected.visible = bool(self.overlay_prop_vars['visible'].get())
    self.refresh_overlay_preview()
    self.refresh_overlay_timeline()
    self.refresh_overlay_property_panel()


def is_overlay_props_widget(self, widget):
    panel = getattr(self, 'overlay_props_inner', None)
    while widget is not None:
        if widget is panel:
            return True
        widget = getattr(widget, 'master', None)
    return False


def on_overlay_props_mousewheel(self, event):
    if not hasattr(self, 'overlay_props_canvas') or not self.overlay_props_canvas or not self.overlay_props_canvas.winfo_exists():
        return
    if not self._is_overlay_props_widget(getattr(event, 'widget', None)):
        return
    if getattr(event, 'num', None) == 4:
        units = -3
    elif getattr(event, 'num', None) == 5:
        units = 3
    else:
        delta = getattr(event, 'delta', 0)
        if delta == 0:
            return
        units = int(-1 * (delta / 120)) * 3
        if units == 0:
            units = -3 if delta > 0 else 3
    self.overlay_props_canvas.yview_scroll(units, 'units')
    return 'break'
