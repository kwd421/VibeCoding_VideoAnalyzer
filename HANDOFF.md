# VibeCoding_VideoAnalyzer Handoff

## Purpose
- Preserve current working context across sessions and machines.
- Give the next agent a stable, practical picture of what exists now.
- Separate proven behavior from experimental or partially verified behavior.

## Read First
- `CODEX.md`
- `GEMINI.md`
- `DEPLOYMENT.md`

## Current Project Direction
- The project is no longer just an STT/subtitle tool.
- It now has a growing overlay/timeline editing path layered on top of the existing subtitle workflow.
- Current strategy is additive and hybrid:
  - keep the legacy subtitle flow alive,
  - add overlay-based editing in parallel,
  - avoid big-bang replacement.

## Current Stable Core
- Main entry: `main.py`
- Main UI shell: `gui_app.py`
- Transcription/ASR engine: `engine_core.py`
- Player wrapper: `video_player.py`
- Subtitle/block editor: `ui_block_editor.py`
- Render/export path: `video_editor.py`
- Orchestration: `analysis_controller.py`

## Overlay/Timeline State
- `overlay_manager.py`
  - owns `OverlayItem`, `TimelineTrack`, `OverlayManager`
  - supports image/text overlays and selection/layer management
- `subtitle_overlay_adapter.py`
  - maps existing `results_data` rows into transient `subtitle` overlay items
  - uses override maps instead of mutating transcript source data
- `gui_app.py`
  - has `Overlay Timeline` tab
  - supports:
    - ImageOverlay preview
    - TextOverlay preview
    - Subtitle adapter preview behind a toggle
    - overlay selection
    - move/resize for image/text preview items
    - ghost-box resize for smoother UX
    - layer ordering
    - visible toggle
    - delete for manual image/text overlays
    - timeline playhead
    - timeline move and trim
    - 0.1s snapping
    - scrollable overlay properties panel
- `video_editor.py`
  - renders image/text/subtitle overlay items into exported video
  - existing ASS path is still present and should remain untouched unless explicitly changing subtitle export behavior

## Behavior That Has Been Explicitly Preserved
- Existing `results_data` / `Treeview` / block editor structure remains in place.
- Existing ASS-based subtitle render/export path remains available.
- Existing analysis flow remains separate from overlay editing.
- Word-sync experiments that caused regressions were rolled back earlier and should stay isolated if revisited.

## Important Current UX/Architecture Decisions
- Subtitle adapter is not full subtitle-system replacement.
- Subtitle adapter edits are limited and use override maps, not transcript mutation.
- Overlay preview uses a viewport-aware coordinate mapping so window resize does not corrupt stored geometry.
- Resize drag uses ghost-box preview to avoid repeated image regeneration.
- `update_loop()` remains 16ms for playback/highlight accuracy.
- Overlay full refresh is no longer tied directly to every 16ms loop iteration.

## What Is Proven vs. What Is Not

### Proven Recently
- ImageOverlay preview/render path
- Multiple image overlays with layer ordering
- TextOverlay preview/render path
- Text color, font size, wrapping, left/center alignment
- Subtitle adapter preview/timeline/render path
- Subtitle adapter limited style/position/time overrides
- Timeline playhead
- Timeline move/trim with 0.1s snapping
- Overlay property panel scrolling
- Bottom playback controls visible at default window size
- Delete selected image/text overlay
- Ghost-box resize performance path

### Still Limited / Not Fully Mature
- Overlapping timeline item selection is still topmost-first and not ideal.
- Subtitle adapter overrides are session-memory data, not durable project storage.
- Overlay timeline is minimally editable, not a full NLE timeline.
- No keyframes, fade curves, rotation editing, or audio overlay editing.
- No robust project save/load model for overlay state yet.

## String/Encoding Handoff Notes
- Korean UI strings in this repository are easy to break through shell replacement or partial patching, especially inside `gui_app.py`.
- Future Korean UI repair must avoid shell literal replacement, stay separate from feature edits, and verify actual widget text values.
- Temporary English substitution is not a real fix for Korean UI regression.
- `gui_app.py` user-facing strings should be checked against actual on-screen widget text, not only source text.
- `gui_app.py` is now stored as UTF-8 again; the emergency `latin-1` dependency was removed after execution-safe normalization.
- Some internal comments are still mojibake and can be cleaned up later, but the current priority state is: runnable source + correct Korean UI labels.
- `gui_app.py` previously suffered from encoding damage, broken literals, and non-printable characters; it has been brought back to a runnable state through targeted recovery.
- User-facing UI should stay Korean by default; future sessions should treat UI language regressions as real regressions, not cosmetic cleanup.
- When string damage reappears, prioritize execution stability and correct on-screen labels before comment beautification.
- After any string or encoding change, re-run `py_compile`, import, app creation, and a basic UI label check together.

## Recent gui_app.py Damage Incident
- During `test` folder cleanup, root `.py` files were accidentally moved because filename-pattern matching was used before confirming file role.
- Future test cleanup should use an artifact whitelist, keep `.py` files excluded by default, and report the planned move list before anything is moved.
- User approval should come before executing the actual move operation.
- Do not treat "not currently found by import search" as proof that a root source file is disposable.
- Core root source files should stay excluded from test cleanup unless the user explicitly asks otherwise.

- `gui_app.py` recently suffered major damage after an unsafe line-range overwrite edit.
- Recovery then proceeded from a known-good baseline file rather than guessing from the damaged fragment.
- Future `gui_app.py` edits must use context-based patching only.
- Large-file edits require a backup first and `py_compile` / import / app creation checks immediately after the edit.
- String/encoding repair and feature work should be split into separate tasks whenever possible.
- If file size drops unexpectedly, imports fail, or major classes disappear, stop immediately and report the damage before continuing.

## Known Active Concerns
- Word highlight sync is still imperfect and should not be touched casually.
- The overlay system is now usable, but selection ergonomics in overlapping cases still need refinement.
- Documentation had drifted behind implementation; this file and `DEPLOYMENT.md` were refreshed to catch up.

## Current User Priorities
- Function breakage is unacceptable.
- Keep changes small and verifiable.
- Prefer proven behavior over ambitious refactors.
- Do not remove legacy subtitle functionality while overlay features are still maturing.
- The user prefers concrete verification over claims of correctness.

## Suggested Next-Session Workflow
1. Read `CODEX.md`.
2. Read this file.
3. Check `git status`.
4. Distinguish:
   - stable UX fix,
   - small overlay/timeline extension,
   - risky experimental work.
5. Preserve existing render, subtitle, and playback paths unless the task explicitly targets them.

## Files Worth Inspecting Next
- `gui_app.py`
  - overlay timeline UI
  - overlay property panel
  - viewport/preview layout
  - playback/update loop
- `overlay_manager.py`
  - item model, selection, ordering, geometry conversion
- `subtitle_overlay_adapter.py`
  - transient subtitle overlay mapping and override application
- `video_editor.py`
  - overlay render path
- `ui_block_editor.py`
  - legacy subtitle/word editing path

## Deployment Notes Summary
- Build with `build_release.bat`
- Current build strategy still relies on the existing frozen app pipeline
- Overlay/text/subtitle-adapter features should be included in the app because they live in `gui_app.py`, `overlay_manager.py`, `subtitle_overlay_adapter.py`, and existing render modules
- If packaging is revisited, verify that these newer modules are included in the frozen build

## Current Non-Code Diff Notes
- Preview subtitle temp files like `temp_preview_A.ass` and `temp_preview_B.ass` can change during normal app usage.
- Render test artifacts may also appear in the project root during development/testing.

## Refactor Status (2026-03-13)
- Refactoring stage 1 is partially complete.
  - Safe modules have been moved under `app/` and `tools/`.
  - The project is currently in a mixed state: some modules are still at the root, while others are imported from `app.*`.
- Refactoring stage 2 is also partially complete.
  - `event_dispatcher.py`, `vision_processor.py`, `video_player.py`, `overlay_manager.py`, and `timeline_manager.py` now live under `app/`.
- Root runtime files still in place:
  - `main.py`
  - `gui_app.py`
  - `engine_core.py`
  - `analysis_controller.py`
  - `video_editor.py`
  - `ui_block_editor.py`
- Do not assume that every previously implemented overlay/timeline enhancement is still fully verified after the recovery + refactor sequence.

## Current Verified Runtime Status
- `py_compile` succeeds for:
  - `main.py`
  - `gui_app.py`
  - `engine_core.py`
  - `analysis_controller.py`
  - `video_editor.py`
  - moved `app/` modules used by the runtime path
- Import succeeds for:
  - `main`
  - `gui_app`
  - `engine_core`
  - `analysis_controller`
  - `video_editor`
  - moved `app.*` modules currently referenced
- `CustomModelApp(...)` creation succeeds with a dummy player stub.
- Minimal runtime path is back to:
  - compile
  - import
  - app create
  - main-process launch survival

## Current Runtime Problems To Treat As Real
- Do not trust source search alone for Korean UI recovery.
- In the most recent real widget-text check, runtime UI still showed mojibake in some places even though parts of the source had already been normalized.
- Specifically, the latest app-create inspection showed:
  - notebook tab labels still broken at runtime
  - `분석 시작` / `작업 중지` equivalent button texts still broken at runtime
- That means Korean UI is **not fully restored in practice yet**, even if portions of the file look fixed in source form.

## What The Next Session Should Do First
1. Do **not** add new features first.
2. Re-verify actual runtime widget text values in `gui_app.py`.
3. Fix Korean UI at runtime before more overlay/selection bug work.
4. Re-check the minimum overlay path end-to-end:
   - image overlay preview
   - text overlay preview
   - overlay timeline
   - export collection
5. Only after that, continue preview/selection bug fixes.

## Current Bug Queue To Resume After Runtime UI Verification
1. `ImageOverlay` rotation still looks wrong on the real screen.
2. Clicking outside after preview-based image selection can still hide/desync the image.
3. Layer ordering is still unreliable in some multi-image cases.
4. Preview-based selection clear and timeline-based selection clear do not fully match.
