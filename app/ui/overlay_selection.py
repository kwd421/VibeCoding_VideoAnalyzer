import tkinter as tk


def clear_overlay_selection_visuals(self):
    try:
        self.preview_overlay_canvas.delete('selection_marker')
    except tk.TclError:
        pass
    self.overlay_resize_handle.place_forget()
    self.overlay_rotate_handle.place_forget()
    for item_id, label in list(self._overlay_label_refs.items()):
        if not label.winfo_exists() or not isinstance(label, tk.Label):
            continue
        try:
            label.configure(highlightthickness=0, bd=0, relief='flat')
        except tk.TclError:
            pass


def set_selected_overlay(self, item_id, refresh_preview=True, refresh_timeline=True):
    self.overlay_manager.set_selected(item_id)
    if refresh_preview:
        self.refresh_overlay_preview()
    if refresh_timeline:
        self.refresh_overlay_timeline()
    self.refresh_overlay_property_panel()


def clear_selected_overlay(self, refresh_preview=True, refresh_timeline=True):
    self.overlay_manager.set_selected(None)
    self._overlay_drag = {'item_id': None, 'mode': None, 'start_x': 0, 'start_y': 0, 'origin': None}
    self._clear_overlay_selection_visuals()
    if refresh_preview:
        self.refresh_overlay_preview()
    if refresh_timeline:
        self.refresh_overlay_timeline()
    self.refresh_overlay_property_panel()
