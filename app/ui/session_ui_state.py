def handle_progress(app, task):
    app.progress_var.set(task["value"])
    app.lbl_status.config(text=task["text"])


def handle_complete(app, task):
    app.lbl_status.config(text=task["text"], fg=app.C['green'])
    app.progress_var.set(100)
    app.btn_analyze.configure(state='normal')
    has_results = bool(app.results_data)
    if task.get("is_vad") or task.get("is_whisper") or has_results:
        app.save_frame.pack(fill='x', pady=5, before=app.lbl_status)
        for button in [app.btn_fast_save, app.btn_pro_save]:
            button.configure(state='normal')

    if task.get("is_whisper"):
        app.apply_preview_subtitles()
    app.btn_stop.configure(state='disabled')


def reset_action_button(app):
    app.save_frame.pack_forget()
    app.btn_analyze.configure(text='분석 시작', command=app.on_start_analysis, state='normal')
    app.btn_fast_save.configure(state='normal')
    app.btn_pro_save.configure(state='normal')


def set_analysis_start_state(app):
    app.analysis_session.clear_if_finished()
    app.stop_event = app.analysis_session.reset_stop_event()
    app.btn_analyze.configure(state='disabled')
    app.btn_stop.configure(state='normal')
    app.progress_var.set(0)
    app.results_data = []
    for item in app.tree.get_children():
        app.tree.delete(item)


def set_stop_requested_state(app):
    app.lbl_status.config(text='진행 중인 작업을 중지하는 중...', fg=app.C['red'])
    app.btn_stop.configure(state='disabled')
    app.root.after(1500, lambda: reset_action_button(app) or app.lbl_status.config(text='작업이 중지되었습니다.', fg=app.C['red']))

