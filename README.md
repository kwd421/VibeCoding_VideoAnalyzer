# VibeCoding_VideoAnalyzer

Local video transcription and subtitle editing app built with Tkinter, VLC, Faster-Whisper, VAD, and FFmpeg-based tooling.

## Entry Points
- App entry: `main.py`
- Main UI: `gui_app.py`
- Playback wrapper: `video_player.py`
- Transcription engine: `engine_core.py`
- Timeline state: `timeline_manager.py`

## Current Platform Status
- Windows packaging flow exists via `build_release.bat` and `VibeAnalyzer.spec`.
- macOS compatibility work has started and the VLC embed path is now platform-aware.
- macOS runtime is not yet fully verified because the current machine is missing the project Python environment and required packages.

## macOS Runtime Check Status
Verified on 2026-03-20 in this workspace:
- `python3` is available: `Python 3.9.6`
- `.venv` is missing
- dependency manifest such as `requirements.txt` or `pyproject.toml` is missing
- `models/` directory is missing
- import checks currently fail for: `vlc`, `numpy`, `torch`, `faster_whisper`, `imageio_ffmpeg`, `transformers`, `silero_vad`, `noisereduce`, `PIL`
- `tkinter` import succeeds, but GUI window launch was not verifiable in this sandbox

## macOS Bring-Up Checklist
1. Create a local virtual environment.
2. Install the project dependencies into that environment.
3. Install VLC on macOS and confirm the Python `vlc` package can find the VLC runtime.
4. Restore or download the local speech models into `models/` if local bundled models are expected.
5. Run `python main.py` from the project root.
6. Verify video preview, subtitle preview, analysis start, and export paths.

## Recommended macOS Smoke Test
1. Launch the app from the project root.
2. Select a short local `.mp4` file.
3. Confirm the splash screen appears and the main window opens.
4. Confirm video playback renders inside the app window.
5. Start a basic transcription run using CPU mode.
6. Confirm subtitle rows populate and preview subtitles appear in VLC playback.
7. Export `SRT` and confirm the file is created correctly.

## Notes
- `build_release.bat` is Windows-only.
- `VibeAnalyzer.spec` now exists again, but packaging should be re-validated later on an actual build machine.
- See `DEPLOYMENT.md` for packaging notes and `HANDOFF.md` for current project context.
