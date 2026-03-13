# CODEX Rules for VibeCoding_VideoAnalyzer

## Role
- This file defines repository-specific engineering rules.
- It covers architecture boundaries, behavior-preservation rules, and domain-specific guardrails.
- Workflow, validation posture, and reporting style live in `AGENTS.md`.

## Purpose
- Keep behavior stable first.
- Prefer small, reversible changes over broad rewrites.
- Optimize only after preserving current user-facing behavior.

## Architecture Boundaries
- `gui_app.py`: UI composition, playback-facing UI state, overlay/timeline UI, preview coordination.
- `analysis_controller.py`: orchestration between UI requests and engine/render backends.
- `engine_core.py`: ASR/model coordination and transcript generation.
- `video_player.py`: VLC-backed playback wrapper.
- `ui_block_editor.py`: legacy word/block editing UI.
- `video_editor.py`: export/render path.
- `overlay_manager.py`: overlay item storage, selection, ordering, preview geometry conversion.
- `subtitle_overlay_adapter.py`: thin mapping layer from existing subtitle data into overlay-like subtitle items.

## Clean Code Baseline
- Use names that reveal intent immediately. Avoid vague names like `data`, `temp`, `do_work`, `value2`.
- Keep functions small and focused on one reason to change.
- Read top-to-bottom. Higher-level flow should call lower-level helpers instead of mixing every detail inline.
- Prefer guard clauses to deep nested `if/else`.
- Hide duplication when the duplicated logic represents one concept, not just matching text.
- Keep side effects explicit. A function that mutates state, touches files, updates UI, or starts threads should make that obvious.
- Pass as few parameters as practical. If related options keep traveling together, group them in a typed object.
- Replace magic numbers with named constants when the meaning is not obvious from local context.
- Comments should explain intent, constraints, or non-obvious tradeoffs. Do not comment what the code already says clearly.
- Format consistently so scanning the file is easy: same naming style, same error-handling style, same data shape.

## Error Handling
- Do not swallow exceptions unless failure is truly non-critical and intentionally ignorable.
- If an exception is suppressed, keep the scope narrow and leave a clear fallback path.
- Prefer failing safely over continuing in a partially corrupted state.
- User-visible errors should be actionable and specific.

## Refactoring Safety
- No big-bang refactoring.
- Change one responsibility at a time and preserve existing data contracts.
- If a refactor touches thread, media, subtitle timing, file export, preview mapping, or overlay timing logic, keep the old path verifiable until the new path is proven.
- When behavior must stay identical, favor extraction and consolidation over algorithm replacement.

## Existing Subtitle System Rules
- Keep `results_data`, `Treeview`, block editor, and ASS export alive unless the task explicitly changes them.
- Subtitle adapter work must stay additive until the user requests deeper migration.
- Do not move subtitle content editing away from the existing subtitle editing path unless explicitly requested.
- Preserve subtitle readability: split long text conservatively, avoid tiny trailing fragments, keep timing changes physically plausible.

## Overlay And Timeline Rules
- Treat the overlay system as additive. Do not replace the legacy subtitle path unless the user explicitly requests that migration.
- Prefer thin adapter layers over rewriting transcript data structures.
- Preview coordinates and render coordinates must remain distinct. Store stable render-space geometry and derive preview placement from viewport transforms.
- Keep preview-render behavior consistent. Preview edits should map cleanly into render inputs without hidden per-window state.
- Layer, visible, and timing rules should stay consistent across preview, timeline, export collection, and final render.
- Timeline edits should update the smallest authoritative state possible:
  - manual image/text overlays update overlay items directly,
  - subtitle adapter changes update override maps, not transcript source rows.

## UI Language And Encoding Rules
- Do not insert Korean literals into `gui_app.py` through shell inline replace commands.
- Read UTF-8 files as UTF-8 and write them back as UTF-8 only.
- Korean UI string repairs should target actual widget creation/configure calls, string constants, or explicit label maps; unclear partial replacement is forbidden.
- English substitution is not considered a completed recovery for broken Korean UI.
- Korean UI repair turns must report actual widget text verification, not just source-level replacement.
- If Korean UI strings remain scattered, note that longer-term string centralization is still needed.
- `gui_app.py` has been normalized back to UTF-8; future edits should keep it UTF-8 unless a recovery task explicitly requires otherwise.
- The default user-facing UI language in this repository is Korean.
- When editing large files like `gui_app.py`, preserve source encoding first and avoid bulk string replacement without verification.
- UI string changes must be verified for label, button, tab, and dialog regressions in addition to behavior checks.
- Do not leave broken Korean strings in temporary English unless the follow-up Korean normalization is completed in the same task or explicitly handed off.

## gui_app.py Safety Rules
- Treat `gui_app.py` as a high-risk file.
- Do not use line-number-based partial replacement when editing `gui_app.py`.
- Use function-scoped replacement, unique anchor-based patching, or context-based edits only.
- Before large `gui_app.py` edits, secure a recovery baseline or backup copy.
- After risky `gui_app.py` edits, immediately run `py_compile`, import, and app creation verification.
- If `gui_app.py` is damaged, prefer the most recent known-good baseline over fragment-based guess recovery.

## String/Encoding Work Rules
- Do not perform test-file cleanup or relocation based only on filename patterns.
- Limit move candidates to a whitelist of artifact files and temporary folders.
- Root source files such as `gui_app.py`, `main.py`, `analysis_controller.py`, `overlay_manager.py`, `video_editor.py`, `timeline_manager.py`, `text_sanitizer.py`, and `text_overlay_utils.py` are excluded from test cleanup by default.
- Unless the user explicitly requests it, do not move `.py`, `.md`, configuration files, or project documentation into a `test` folder.
- Before any move, produce a dry-run style planned move list and report it first.
- After any move, verify that key root source files still exist where they started and that minimal compile/import checks still pass.
- Do not decide that a source file is inactive or unnecessary only because current import search does not show it.

- Keep string/encoding repair separate from feature changes whenever possible.
- The default user-facing UI language in this repository is Korean.
- If encoding problems occur, restore execution first, then explicitly verify UI language regressions.
- Do not leave temporary English replacements in place without either restoring Korean in the same task or documenting the planned follow-up.

## UI And Threading Rules
- UI updates must never be performed directly from worker threads. Use the dispatcher/UI-queue path.
- Stop actions should be non-blocking and return control quickly.
- High-frequency playback loops must stay optimized for timing accuracy first.
- Overlay redraws should be conditional or localized, not tied blindly to every playback tick.
- During interactive resize, prioritize responsiveness over live image fidelity. Ghost-box or deferred high-quality redraw strategies are preferred.

## Performance Rules
- Measure hotspot patterns before changing behavior-heavy code.
- Prefer removing repeated O(n) work from high-frequency UI loops before touching model logic.
- Avoid unnecessary disk I/O in analysis paths when data can stay in memory.
- Limit thread fan-out around heavy inference code; more threads are not automatically faster.
- For overlay preview work, optimize drag/resize paths before touching export correctness paths.

## Review Priorities
- First: bugs, races, corrupted state, broken exports, broken playback, timing drift, preview-render mismatch.
- Second: hidden coupling, duplicated logic, maintainability debt.
- Third: performance opportunities that do not change behavior.

## Delegation Rule
- Any implementation request sent to another model must include behavior-preservation requirements, touched files, explicit non-goals, validation steps, and rollback guidance if playback, transcription, subtitle preview, overlay preview, timeline editing, or export could be affected.

## Source Notes
- Clean code guidance adapted from the Naver Cloud Platform Medium article on clean code.
- Project-specific operating rules adapted from `GEMINI.md` and the repository's current hybrid subtitle/overlay architecture.
