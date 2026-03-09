# Deployment Guide

## What Changed
- The app now resolves bundled models from the executable folder first.
- Default model selection now prefers the bundled local Faster-Whisper model instead of remote download.
- Runtime paths that used to rely on the current working directory now use the executable location when frozen.

## Build
1. Open a terminal in the project root.
2. Run `build_release.bat`.
3. Wait for PyInstaller to finish.
4. Use the folder `dist/VibeAnalyzer_Alpha` as the release artifact.

## What To Copy To Another PC
- Copy the whole folder `dist/VibeAnalyzer_Alpha`.
- Do not copy only `VibeAnalyzer_Alpha.exe`.
- Keep `_internal` next to the executable.

Expected layout:
- `VibeAnalyzer_Alpha/VibeAnalyzer_Alpha.exe`
- `VibeAnalyzer_Alpha/_internal/models/...`
- `VibeAnalyzer_Alpha/_internal/params.txt`

## First Test On Another PC
1. Launch `VibeAnalyzer_Alpha.exe`.
2. Select a short local video file.
3. Keep the console visible.
4. Start analysis.
5. Confirm that analysis progresses without waiting on Hugging Face downloads.

## Healthy Signs
- The app opens normally.
- Video preview works.
- Analysis starts after selecting a video.
- Console may show warnings, but should not stall on model download.
- Bundled model loading should prefer local files.

## Warnings That Are Usually Not Fatal
- `WhisperX module not found`
- Hugging Face symlink warnings
- VLC `direct3d11` warnings followed by DXVA2 fallback
- `nvcuda.dll` missing on a non-NVIDIA machine

## Signs Of A Real Packaging Problem
- Selecting a video does nothing and no progress starts.
- The app tries to download `large-v3-turbo` from the internet on first analysis.
- `_internal/models` is missing from the release folder.
- The executable was copied without the `_internal` folder.

## Quick Troubleshooting
1. Check that `_internal/models/Whisper-Large-v3-turbo-STT-Zeroth-KO-v2` exists.
2. Re-copy the entire `dist/VibeAnalyzer_Alpha` folder.
3. Test with the default local model first.
4. If the target PC is weak, switch the device option to CPU and retry.
5. If analysis still does not start, capture the full console log after pressing analyze.

## Notes
- Current successful local build command: `.venv\\Scripts\\pyinstaller.exe VibeAnalyzer.spec --clean --noconfirm`
- `--clean` helps remove stale build artifacts, but does not by itself guarantee Microsoft SmartScreen will never appear.
- SmartScreen behavior is mainly affected by file reputation and code signing.
- Build output verified on 2026-03-09.
