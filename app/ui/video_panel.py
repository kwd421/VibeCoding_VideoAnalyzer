def toggle_play(app):
    if app.player:
        is_playing = app.player.toggle_play()
        app.btn_play.config(text='일시정지' if is_playing else '재생')
        app._sync_audio_clip_playback(force_seek=True)


def skip_time(app, ms):
    if app.player:
        app.player.skip(ms)


def on_seek_start(app, event):
    app.is_seeking = True
    app._was_playing_before_seek = app.player.is_playing() if app.player else False
    app._sync_audio_clip_playback(force_seek=True)
    if app.player:
        app.player.set_mute(True)
        if not app._was_playing_before_seek:
            app.player.toggle_play()
    update_seek_from_mouse(app, event)


def on_seek_motion(app, event):
    if app.is_seeking:
        update_seek_from_mouse(app, event)


def on_seek_release(app, event):
    if app.is_seeking:
        update_seek_from_mouse(app, event)
    app.is_seeking = False
    if app.player:
        if getattr(app, '_was_playing_before_seek', False):
            app.player.play()
        else:
            app.player.pause()
        app.root.after(100, lambda: app.player.set_mute(False) if app.player else None)
    app._sync_audio_clip_playback(force_seek=True)


def update_seek_from_mouse(app, event):
    try:
        width = app.seek_bar.winfo_width()
        if width > 0 and app.player:
            pos = max(0.0, min(1.0, event.x / width))
            app.player.set_position(pos)
            app.seek_var.set(pos * 1000)
    except Exception as exc:
        print(f'[WARN] seek update error: {exc}')

