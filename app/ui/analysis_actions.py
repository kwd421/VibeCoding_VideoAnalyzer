import threading

from app.models.config_models import AnalysisSettings


def load_engine_async(app):
    threading.Thread(target=app.controller.init_engine, daemon=True).start()


def stop_action(app):
    app.analysis_session.request_stop()
    if app.stop_event and not app.stop_event.is_set():
        app.stop_event.set()
    from app.ui.session_ui_state import set_stop_requested_state

    set_stop_requested_state(app)


def start_analysis(app):
    mode = app.mode_var.get()
    selected_model = app.ai_model_var.get().split(" ")[0]
    app.engine.set_model_id(selected_model)

    try:
        min_sil_ms = int(app.silence_dur_var.get() * 1000)
        pad_ms = int(app.speech_pad_var.get() * 1000)
    except Exception:
        min_sil_ms, pad_ms = 2000, 250

    device_val = app.device_var.get()
    if "auto" in device_val:
        mapped_dev = "auto"
    elif "cuda" in device_val:
        mapped_dev = "cuda"
    elif "mps" in device_val:
        mapped_dev = "mps"
    elif "25%" in device_val:
        mapped_dev = "cpu_25"
    elif "50%" in device_val:
        mapped_dev = "cpu_50"
    elif "75%" in device_val:
        mapped_dev = "cpu_75"
    else:
        mapped_dev = "cpu"

    analysis_options = AnalysisSettings(
        beam_size=app.beam_size_var.get(),
        use_denoise=app.use_denoise_var.get(),
        use_dominant=app.use_dominant_var.get(),
        language=app.lang_var.get().split("(")[-1].replace(")", "").strip(),
        vad_threshold=app.vad_threshold_var.get(),
        min_silence_ms=min_sil_ms,
        speech_pad_ms=pad_ms,
        use_word_timestamps=True,
        use_whisper_vad=app.use_whisper_vad_var.get(),
        use_silero_vad=app.use_silero_vad_var.get(),
        use_whisperx_align=getattr(app, 'use_whisperx_var', None).get() if getattr(app, 'use_whisperx_var', None) is not None else False,
        remove_punctuation=getattr(app, 'remove_punctuation_var', None).get() if getattr(app, 'remove_punctuation_var', None) is not None else False,
        device_mode=mapped_dev,
    )

    from app.ui.session_ui_state import set_analysis_start_state

    set_analysis_start_state(app)
    max_chars = app.max_len_int.get()
    app.analysis_session.start(
        app.controller.run_analysis,
        args=(app.current_video_path, app.stop_event, mode, min_sil_ms, pad_ms, max_chars, analysis_options),
        daemon=True,
        name="analysis-worker",
    )

