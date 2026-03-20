# VibeCoding_VideoAnalyzer Handoff

## Purpose
- Preserve working context across machines and sessions.
- Help the next agent understand what is stable, what was attempted, and what to avoid.

## Project Snapshot
- Project: `VibeCoding_VideoAnalyzer`
- Main app entry: `main.py`
- Main UI: `gui_app.py`
- Transcription engine: `engine_core.py`
- Word/block editor: `ui_block_editor.py`
- Playback wrapper: `video_player.py`
- Timeline state: `timeline_manager.py`

## Rules To Read First
- `CODEX.md`
- `GEMINI.md`

## Current Stable Changes
- Startup splash screen with visible progress was added in `main.py`.
- New video selection now clears previous transcript/block state in `gui_app.py`.
- `video_player.py` now uses platform-aware VLC embedding:
  - macOS: `set_nsobject`
  - Windows: `set_hwnd`
  - Linux: `set_xwindow`
- Linux-only VLC option `--no-xlib` is no longer forced on macOS.
- Subtitle color picker calls were fixed to use `from tkinter import colorchooser`.
- macOS undo/redo bindings were added with `Command` shortcuts.
- Temp file cleanup is scoped to the script directory instead of the process CWD.
- Frozen builds now resolve runtime paths from the executable directory.
- Bundled Faster-Whisper models are preferred over remote download when available.
- `VibeAnalyzer.spec` was recreated so the Windows build script has a real target again.
- Deployment notes are documented in `DEPLOYMENT.md`.

## Current macOS Status
- Source-level macOS fixes were applied for VLC embedding and a few UI behaviors.
- Runtime is still blocked in this workspace because there is no `.venv` and no installed Python dependencies.
- Repository currently has no dependency manifest such as `requirements.txt` or `pyproject.toml`.
- Repository currently has no `models/` directory, so local-model verification is not possible yet.

## Runtime Check Results
Checked on 2026-03-20:
- `python3 --version` -> `Python 3.9.6`
- `tkinter` import succeeds
- GUI window launch was not confirmed in sandbox
- missing imports in the active environment:
  - `vlc`
  - `numpy`
  - `torch`
  - `faster_whisper`
  - `imageio_ffmpeg`
  - `transformers`
  - `silero_vad`
  - `noisereduce`
  - `PIL`

## Recent Sync Experiments
- We attempted word-level sync improvements in `engine_core.py`, `gui_app.py`, and `ui_block_editor.py`.
- Those experiments caused regressions:
  - some word blocks stopped highlighting,
  - sync did not improve reliably,
  - user requested full rollback.
- Result: those sync experiments were reverted.
- Current guidance: do not re-apply word timing changes directly in core paths without a clearly isolated experimental toggle.

## Known Active Concerns
- Word-level highlight sync is still imperfect.
- The user specifically reported:
  - some words highlight too early or too late,
  - the issue is not a simple global offset,
  - prior attempts that changed timing logic made things worse.
- If revisiting this:
  - use an experimental on/off toggle,
  - avoid changing default behavior first,
  - test against real sample clips before keeping changes.

## User Preferences
- Functionality breakage is unacceptable.
- Experimental features should be behind an explicit on/off switch.
- The user values practical behavior over theoretical improvements.
- Explanations should be clear and concrete, especially when something changed or regressed.
- Build validation can wait, but macOS source runtime should be validated properly.

## Suggested Workflow For Next Session
1. Read `CODEX.md` and `GEMINI.md`.
2. Read this file.
3. Check `git status`.
4. If working on macOS runtime, restore a usable Python environment first.
5. Install missing dependencies and restore `models/` before judging runtime behavior.
6. Keep risky sync logic behind toggles.

## Files Worth Inspecting For Future Work
- `main.py`: startup splash and boot flow
- `gui_app.py`: analysis option wiring, state reset, playback loop, UI state
- `engine_core.py`: ASR pipeline and word timestamp generation
- `ui_block_editor.py`: active word highlighting logic
- `video_player.py`: VLC timing behavior and platform embedding

## Testing Notes
- For startup behavior, verify the splash appears before heavy import work and reaches 100%.
- For new video loading, verify old transcript rows and word blocks are cleared.
- For macOS runtime, verify VLC video renders inside the Tk window and subtitle preview still works.
- For sync work, always test on a real problematic sample, not just synthetic assumptions.
- If sync work is experimental, provide a rollback path and default it to off.

## Current Non-Code Diffs
- Temporary preview subtitle files like `temp_preview_A.ass` and `temp_preview_B.ass` may be modified during app usage.
- These are generated artifacts, not core source changes.
