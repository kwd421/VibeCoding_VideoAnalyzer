# Deployment Guide

## Current Scope
- Windows packaging flow is the only documented release flow in this repository right now.
- `VibeAnalyzer.spec` exists and is referenced by `build_release.bat`.
- macOS runtime verification is in progress, but macOS packaging is not documented or validated yet.

## Windows Build
1. Open a terminal in the project root.
2. Ensure `.venv\Scripts\python.exe` exists.
3. Ensure `.venv\Scripts\pyinstaller.exe` exists.
4. Run `build_release.bat`.
5. Use `dist/VibeAnalyzer_Alpha` as the release artifact.

## Windows Release Layout
- Copy the whole `dist/VibeAnalyzer_Alpha` folder.
- Do not copy only `VibeAnalyzer_Alpha.exe`.
- Keep `_internal` next to the executable.

Expected layout:
- `VibeAnalyzer_Alpha/VibeAnalyzer_Alpha.exe`
- `VibeAnalyzer_Alpha/_internal/models/...`
- `VibeAnalyzer_Alpha/_internal/params.txt`

## Windows First Test
1. Launch `VibeAnalyzer_Alpha.exe`.
2. Select a short local video file.
3. Keep the console visible.
4. Start analysis.
5. Confirm analysis progresses without waiting on remote model download.

## Windows Healthy Signs
- The app opens normally.
- Video preview works.
- Analysis starts after selecting a video.
- Console may show warnings, but should not stall on model download.
- Bundled model loading should prefer local files.

## Windows Warnings That Are Usually Not Fatal
- `WhisperX module not found`
- Hugging Face symlink warnings
- VLC `direct3d11` warnings followed by DXVA2 fallback
- `nvcuda.dll` missing on a non-NVIDIA machine

## Windows Signs Of A Real Packaging Problem
- Selecting a video does nothing and no progress starts.
- The app tries to download `large-v3-turbo` on first analysis when a bundled local model is expected.
- `_internal/models` is missing from the release folder.
- The executable was copied without the `_internal` folder.

## macOS Runtime Notes
Checked on 2026-03-20:
- macOS source runtime is not currently runnable in this workspace because `.venv` is missing.
- No dependency manifest is present in the repository.
- Required imports are currently missing from the active Python environment, including `vlc`, `numpy`, `torch`, `faster_whisper`, `imageio_ffmpeg`, `transformers`, `silero_vad`, `noisereduce`, and `PIL`.
- `models/` is also missing in this workspace, so local-model startup cannot be validated yet.

## macOS Runtime Checklist
1. Create a macOS virtual environment for the project.
2. Install all runtime dependencies into that environment.
3. Install VLC and verify the Python `vlc` package can load the VLC runtime.
4. Restore the `models/` directory if local model loading is expected.
5. Run `python main.py`.
6. Verify window startup, VLC video embedding, transcription start, subtitle preview, and export.

## Notes
- Current Windows build command in the script is `.venv\\Scripts\\pyinstaller.exe VibeAnalyzer.spec --clean --noconfirm`.
- `build_release.bat` is Windows-only and cannot be used as-is on macOS.
- Packaging should be re-tested later on the actual target build machine.
