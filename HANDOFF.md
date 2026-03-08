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

## Rules To Read First
- `CODEX.md`
- `GEMINI.md`

## Current Stable Changes
- Startup splash screen with visible progress was added in `main.py`.
- New video selection now clears previous transcript/block state in `gui_app.py`.
- `video_player.py` uses a local timeout inside async load wait logic.
- Temp file cleanup is scoped to the script directory instead of the process CWD.

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

## Suggested Workflow For Next Session
1. Read `CODEX.md` and `GEMINI.md`.
2. Read this file.
3. Check `git status`.
4. Confirm whether the user wants stable fixes or experimental features.
5. Keep risky logic behind toggles.

## Files Worth Inspecting For Future Work
- `main.py`: startup splash and boot flow
- `gui_app.py`: analysis option wiring, state reset, playback loop, UI state
- `engine_core.py`: ASR pipeline and word timestamp generation
- `ui_block_editor.py`: active word highlighting logic
- `video_player.py`: VLC timing behavior

## Testing Notes
- For startup behavior, verify the splash appears before heavy import work and reaches 100%.
- For new video loading, verify old transcript rows and word blocks are cleared.
- For sync work, always test on a real problematic sample, not just synthetic assumptions.
- If sync work is experimental, provide a rollback path and default it to off.

## Current Non-Code Diffs
- Temporary preview subtitle files like `temp_preview_A.ass` and `temp_preview_B.ass` may be modified during app usage.
- These are generated artifacts, not core source changes.
