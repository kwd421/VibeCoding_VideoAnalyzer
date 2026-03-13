import tkinter as tk


def bind_keys(self):
    def _is_editing():
        widget = self.root.focus_get()
        return isinstance(widget, (tk.Entry, tk.Text))

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
        if _is_editing():
            return
        if self.overlay_manager.selected_item_id is None:
            return
        self.delete_selected_overlay()
        return "break"

    self.root.bind_all("<space>", _on_space)
    self.root.bind_all("<Left>", _on_left)
    self.root.bind_all("<Right>", _on_right)
    self.root.bind_all("<Control-z>", _on_undo)
    self.root.bind_all("<Control-y>", _on_redo)
    self.root.bind_all("<Control-Z>", _on_redo)
    self.root.bind_all("<Delete>", _on_delete)

    try:
        self.root.unbind_class('TNotebook', '<Left>')
        self.root.unbind_class('TNotebook', '<Right>')
        self.root.unbind_class('Treeview', '<Left>')
        self.root.unbind_class('Treeview', '<Right>')
    except Exception:
        pass
