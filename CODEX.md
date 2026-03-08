# CODEX Rules for VibeCoding_VideoAnalyzer

## Purpose
- Keep behavior stable first.
- Prefer small, reversible changes over broad rewrites.
- Optimize only after preserving current user-facing behavior.

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
- If a refactor touches thread, media, subtitle timing, or file export logic, keep the old path verifiable until the new path is proven.
- When behavior must stay identical, favor extraction and consolidation over algorithm replacement.

## Project Rules Adopted from GEMINI.md
- Respect the modular boundaries: `gui_app.py` for UI composition, `analysis_controller.py` for orchestration, `engine_core.py` for model coordination, `timeline_manager.py` for transcript state.
- UI updates must never be performed directly from worker threads. Use `dispatcher.emit -> root.after`.
- Stop actions should be non-blocking and return control quickly.
- Large temporary arrays or model-side buffers must be released explicitly when no longer needed.
- Keep processing local-only. Do not introduce external API dependencies for core analysis.
- Preserve subtitle readability: split long text conservatively, avoid tiny trailing fragments, keep timing changes physically plausible.

## Performance Rules
- Measure hotspot patterns before changing behavior-heavy code.
- Prefer removing repeated O(n) work from high-frequency UI loops before touching model logic.
- Avoid unnecessary disk I/O in analysis paths when data can stay in memory.
- Limit thread fan-out around heavy inference code; more threads are not automatically faster.

## Review Priorities
- First: bugs, races, corrupted state, broken exports, broken playback, timing drift.
- Second: hidden coupling, duplicated logic, maintainability debt.
- Third: performance opportunities that do not change behavior.

## 5.3 Delegation Rule
- Any implementation request sent to another model must include behavior-preservation requirements, touched files, explicit non-goals, validation steps, and rollback guidance if playback, transcription, subtitle preview, or export could be affected.

## Source Notes
- Clean code guidance adapted from the Naver Cloud Platform Medium article on clean code.
- Project-specific operating rules adapted from `GEMINI.md`.
