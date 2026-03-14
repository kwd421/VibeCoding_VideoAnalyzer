from tkinter import messagebox


def delete_selected_overlay(self):
    selected = self.overlay_manager.get_selected()
    if selected is None or selected.type == 'subtitle':
        return
    if selected.extra.get('primary_video'):
        messagebox.showinfo('안내', '메인영상은 삭제할 수 없습니다.')
        return
    item_id = selected.id
    self.overlay_manager.remove_item(item_id)
    widget = self._overlay_label_refs.pop(item_id, None)
    if widget is not None and widget.winfo_exists():
        widget.destroy()
    refs = self._overlay_canvas_refs.pop(item_id, None)
    if refs:
        for canvas_id in refs.get('markers', []):
            try:
                self.preview_overlay_canvas.delete(canvas_id)
            except Exception:
                pass
        image_id = refs.get('image')
        if image_id:
            try:
                self.preview_overlay_canvas.delete(image_id)
            except Exception:
                pass
    self._overlay_photo_refs.pop(item_id, None)
    self._invalidate_overlay_preview_cache(item_id)
    self.overlay_manager.set_selected(None)
    self.refresh_overlay_preview()
    self.refresh_overlay_timeline()
    self.refresh_overlay_property_panel()


def reorder_selected_overlay(self, direction):
    if self.overlay_manager.move_selected_layer(direction):
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()
