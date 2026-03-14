import tkinter as tk


def is_editing_widget(self):
    widget = self.root.focus_get()
    return isinstance(widget, (tk.Entry, tk.Text))


def handle_delete_key(self, event=None):
    if is_editing_widget(self):
        return
    if self.overlay_manager.selected_item_id is None:
        return
    self.delete_selected_overlay()
    return "break"


def bind_keys(self):
    def _is_editing():
        return is_editing_widget(self)

    def _on_space(e):
        if _is_editing():
            return
        self.toggle_play()
        return "break"

    def _on_left(e):
        if _is_editing():
            return
        self.skip_time(-5000)
        return "break"

    def _on_right(e):
        if _is_editing():
            return
        self.skip_time(5000)
        return "break"

    def _on_undo(e):
        if _is_editing():
            return
        if self.transcript_manager.undo():
            self.rebuild_tree_and_render()
        return "break"

    def _on_redo(e):
        if _is_editing():
            return
        if self.transcript_manager.redo():
            self.rebuild_tree_and_render()
        return "break"

    def _on_delete(e):
        return handle_delete_key(self, e)

    self.root.bind_all("<space>", _on_space)
    self.root.bind_all("<Left>", _on_left)
    self.root.bind_all("<Right>", _on_right)
    self.root.bind_all("<Control-z>", _on_undo)
    self.root.bind_all("<Control-y>", _on_redo)
    self.root.bind_all("<Control-Z>", _on_redo)
    for sequence in ("<Delete>", "<KeyPress-Delete>", "<KP_Delete>"):
        self.root.bind(sequence, _on_delete)
        self.root.bind_all(sequence, _on_delete)
        if hasattr(self, 'overlay_timeline_canvas') and self.overlay_timeline_canvas is not None:
            self.overlay_timeline_canvas.bind(sequence, _on_delete)

    try:
        self.root.unbind_class('TNotebook', '<Left>')
        self.root.unbind_class('TNotebook', '<Right>')
        self.root.unbind_class('Treeview', '<Left>')
        self.root.unbind_class('Treeview', '<Right>')
    except Exception:
        pass
