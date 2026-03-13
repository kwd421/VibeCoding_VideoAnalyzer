# Current Status

## Snapshot Date
- 2026-03-13

## What Is True Right Now
- `gui_app.py` is back to a runnable state.
- The project is in a mixed refactor state:
  - some runtime files are still at the root,
  - some safer/supporting modules were already moved into `app/` and `tools/`.
- We should treat the current state as **recoverable and usable for continued work**, but not as fully re-verified.

## Files Already Moved
- `app/models/config_models.py`
- `app/models/overlay_manager.py`
- `app/models/timeline_manager.py`
- `app/processors/audio_processor.py`
- `app/processors/text_sanitizer.py`
- `app/adapters/subtitle_overlay_adapter.py`
- `app/utils/text_overlay_utils.py`
- `app/utils/event_dispatcher.py`
- `app/services/video_player.py`
- `app/services/vision_processor.py`
- `tools/convert.py`

## Files Still At Root And Still Important
- `main.py`
- `gui_app.py`
- `engine_core.py`
- `analysis_controller.py`
- `video_editor.py`
- `ui_block_editor.py`

## Verified Recently
- `py_compile` passes for the root runtime path and the moved `app/` modules.
- `import` passes for:
  - `main`
  - `gui_app`
  - `engine_core`
  - `analysis_controller`
  - `video_editor`
  - moved `app.*` modules referenced by them
- `CustomModelApp(...)` can be created with a dummy player stub.
- Main-process launch survival was rechecked after the big `gui_app.py` recovery.

## Not Safe To Assume
- Do not assume Korean UI is fully fixed just because source strings look correct.
- Do not assume every overlay/timeline improvement from earlier sessions is still fully verified after recovery and refactor.
- Do not assume preview-selection bugs are fixed.
- Do not assume layer ordering is correct in all cases.

## Current Runtime UI Reality
- The latest direct widget-text inspection still showed runtime mojibake in some places.
- Most important current fact:
  - runtime notebook tab labels were still broken
  - runtime analyze/stop button labels were still broken
- So the next session must verify **actual widget text values**, not just source text.

## Current Risk Areas
- `gui_app.py` remains the highest-risk file.
- Preview selection state vs. image visibility is still fragile.
- Image rotation behavior is still not trustworthy from a real on-screen perspective.
- Layer ordering and selection-source consistency still need focused debugging.

## What The Next Session Should Do First
1. Read:
   - `AGENTS.md`
   - `CODEX.md`
   - `HANDOFF.md`
   - this file
2. Verify actual runtime widget text values in `gui_app.py`.
3. Fix Korean UI at runtime before adding any new behavior.
4. Re-check minimum overlay path:
   - image overlay preview
   - text overlay preview
   - overlay timeline
   - export collection
5. Only then resume bug fixing.

## What The Next Session Should Not Do First
- Do not add new features first.
- Do not keep pushing deeper overlay/rotation changes before runtime Korean UI is re-verified.
- Do not do broad cleanup/moves before current runtime state is confirmed.

## Current Known User-Facing Bug Queue
1. `ImageOverlay` rotation still looks wrong on the actual screen.
2. Clicking outside after selecting an image overlay in preview can still make the image disappear or desync.
3. Multi-image layer ordering is still unreliable.
4. Preview selection clear and timeline selection clear are still not fully consistent.

## Validation Baseline For The Next Session
- `py_compile`
- `import`
- `app create`
- actual widget text checks
- minimum overlay preview check
- minimum overlay timeline check
- minimum export collection check
