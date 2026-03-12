# Deployment Guide

## Scope
- This guide covers building and checking the frozen Windows app.
- It now also reflects the current overlay/timeline/editor state, not just the original subtitle-only workflow.

## Build
1. Open a terminal in the project root.
2. Run `build_release.bat`.
3. Wait for PyInstaller to finish.
4. Use `dist/VibeAnalyzer_Alpha` as the release artifact.

## Current Build Assumptions
- Runtime paths are resolved from the executable folder when frozen.
- Bundled local models are preferred when available.
- The app depends on `customtkinter` in the active environment at build time.
- Recent overlay modules are part of the runtime:
  - `overlay_manager.py`
  - `subtitle_overlay_adapter.py`

## What To Copy To Another PC
- Copy the whole folder `dist/VibeAnalyzer_Alpha`
- Do not copy only `VibeAnalyzer_Alpha.exe`
- Keep `_internal` next to the executable

Expected layout:
- `VibeAnalyzer_Alpha/VibeAnalyzer_Alpha.exe`
- `VibeAnalyzer_Alpha/_internal/models/...`
- `VibeAnalyzer_Alpha/_internal/params.txt`

## First Test On Another PC
1. Launch `VibeAnalyzer_Alpha.exe`
2. Select a short local video file
3. Keep the console visible
4. Start analysis
5. Confirm that analysis progresses without stalling on model download
6. Open the `Overlay Timeline` tab and confirm it appears
7. Add at least one image overlay and one text overlay
8. Verify they appear in preview and can be selected
9. Export a short output clip and confirm the overlay appears in the result

## Healthy Signs
- The app opens normally
- Video preview works
- Analysis starts after selecting a video
- Overlay Timeline tab is visible
- Overlay Properties panel scrolls instead of clipping controls
- Bottom playback controls are visible without manually enlarging the window
- Image/text overlay preview appears and can be selected
- Console may show warnings, but should not stall on model download
- Bundled model loading should prefer local files

## UI Text Regression Checks
- Before shipping, confirm that the default tabs, buttons, and major panel labels are displayed in Korean.
- Verify that `Overlay Properties`, `Overlay Timeline`, and `Subtitle Adapter` related labels are not mojibake or partial fallback text.
- Check another machine or clean environment for Korean text corruption before calling a build ready.
- Treat successful `py_compile`/import as necessary but insufficient; confirm visible UI text in the built app as well.

## Overlay/Timeline Regression Checks
- Add Image Overlay works
- Add Text Overlay works
- Delete Overlay removes manual image/text overlays from:
  - preview
  - overlay timeline
  - export input
- Timeline playhead moves with playback
- Timeline bar move/trim changes exported timing
- Snapping still works if set to `0.1s`
- Subtitle Adapter toggle does not break the legacy subtitle path

## Warnings That Are Usually Not Fatal
- `WhisperX module not found`
- Hugging Face symlink warnings
- VLC `direct3d11` warnings followed by DXVA2 fallback
- `nvcuda.dll` missing on a non-NVIDIA machine

## Signs Of A Real Packaging Problem
- Selecting a video does nothing and no progress starts
- The app tries to download `large-v3-turbo` from the internet unexpectedly
- `_internal/models` is missing from the release folder
- `Overlay Timeline` tab is missing
- Adding overlays works in source run but not in frozen build
- The executable was copied without the `_internal` folder

## Quick Troubleshooting
1. Check that `_internal/models/...` exists
2. Re-copy the entire `dist/VibeAnalyzer_Alpha` folder
3. Test with the default local model first
4. If the target PC is weak, switch the device option to CPU and retry
5. If analysis still does not start, capture the full console log after pressing analyze
6. If overlay export fails, verify that newly added modules were included in the frozen build

## Notes
- Current successful local build command:
  - `.venv\\Scripts\\pyinstaller.exe VibeAnalyzer.spec --clean --noconfirm`
- `--clean` helps remove stale build artifacts, but does not by itself guarantee Microsoft SmartScreen will never appear
- SmartScreen behavior is mainly affected by file reputation and code signing
- This document was refreshed after overlay/timeline/editor features were added so frozen-build checks cover more than the original subtitle workflow
