# VibeCoding Video Analyzer

[한국어 README 보기](README.ko.md)

A local-first desktop video transcription, subtitle editing, preview, and export tool.

The current project is a Python/Tk macOS-focused build of the original video analyzer workflow. It keeps the analysis pipeline local where possible, exposes timing controls for subtitle correction, and now renders preview subtitles directly over the video instead of relying on temporary ASS preview files.

## Preview

[![VibeCoding Video Analyzer preview](https://img.youtube.com/vi/_hM43KQNOYo/maxresdefault.jpg)](https://www.youtube.com/watch?v=_hM43KQNOYo)

[Watch the preview on YouTube](https://www.youtube.com/watch?v=_hM43KQNOYo)

## Current Status

- Main branch in active development: `mac-experiment`
- Runtime target: local desktop app launched from `main.py`
- Preview direction: live in-app subtitle overlay from normalized subtitle cues
- Export direction: subtitle/text exports plus video render/burn support
- Experimental options: WhisperX alignment, Demucs vocal separation, Gemma 4 MLX suspicious-segment filtering

## Features

- Load local video files and run speech analysis.
- Use local transcription backends, including Faster-Whisper style paths and a CoreML/whisper.cpp worker path where configured.
- Optional external VAD, denoise, Demucs vocal separation, and WhisperX forced alignment controls.
- Optional Gemma 4 MLX filter for reviewing suspicious short or hallucinated segments.
- Edit subtitle rows, segment timing, and word blocks.
- Adjust timing with mouse wheel shortcuts, including adjacent-boundary movement for shared subtitle edges.
- Preview subtitles through a live overlay on top of the video player.
- Export subtitles as `SRT`, `VTT`, `TXT`, `CSV`, and `FCPXML`.
- Render video ranges and optionally burn subtitles using FFmpeg drawtext filters generated from subtitle cues.

## Requirements

- macOS is the current active development target.
- Python is required. A `.venv/` virtual environment is recommended for development, but it is not a file that should be downloaded from GitHub.
- VLC and the Python `vlc` package for embedded preview playback.
- FFmpeg access through the runtime dependencies used by the project.
- Local model files under `models/` when using bundled/local model paths.
- Optional packages depend on the selected feature: WhisperX, Demucs, MLX, CoreML/whisper.cpp, denoise, and VAD paths are loaded only when those options are used.

Cloning the repository alone is not enough for a fresh machine yet. The app source is on GitHub, but runtime dependencies, local model files, and the Python environment still need to be installed separately. A packaged app/build artifact is the right path if the goal is "download and run" without setting up Python.

## Run

If you already have a prepared `.venv/`:

```bash
./run.command
```

If dependencies are installed in another Python environment:

```bash
python main.py
```

## Test

```bash
PYTHONPATH=$PWD .venv/bin/python -m unittest tests.test_timing_and_split_rules
```

Useful import/compile smoke check:

```bash
PYTHONPATH=$PWD .venv/bin/python -m py_compile \
  main.py \
  tools/coreml_transcribe_worker.py \
  app/ui/gui_app.py \
  app/ui/ui_block_editor.py \
  app/ui/video_player.py \
  app/engine/engine_core.py \
  app/engine/analysis_controller.py \
  app/engine/audio_processor.py \
  app/engine/vision_processor.py \
  app/core/config_models.py \
  app/core/subtitle_cues.py \
  app/core/timeline_manager.py \
  app/core/text_sanitizer.py \
  app/core/event_dispatcher.py \
  app/core/transcription_backends.py \
  app/media/video_editor.py
```

## Notes For Contributors

- Keep runtime-generated media, previews, model weights, and backup files out of git.
- Preserve editor-visible subtitle timing as the source of truth for preview and export.
- Avoid reintroducing temporary ASS preview files into the live preview path.
- Treat experimental options as opt-in and transparent: failures should be visible rather than hidden by unrelated fallbacks.
- When moving code, keep imports package-based under `app.*` so packaged builds and worker scripts stay predictable.
