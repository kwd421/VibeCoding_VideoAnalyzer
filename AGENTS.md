# AGENTS.md

## Role
- This file defines how to work in this repository.
- It covers workflow, verification discipline, and reporting style.
- Project-specific technical rules live in `CODEX.md`.

## Core working rules
- Always analyze the current code and affected files before editing.
- Preserve existing working behavior unless the requested task explicitly changes it.
- Prefer minimal, high-confidence diffs over large refactors.
- Do not claim something works unless it was actually verified.
- If verification is incomplete, explicitly mark it as partially verified or unverified.

## Required workflow
1. Briefly identify the scope and likely impact before making changes.
2. Make the smallest safe implementation that satisfies the request.
3. Verify both the target behavior and nearby affected behavior.
4. Report what changed, what was verified, and what remains uncertain.

## Validation requirements
- Do not stop at import success or app launch success.
- When UI or media behavior is involved, verify actual behavior, not just code shape.
- Prefer real execution evidence over assumptions.
- Keep existing features working unless the task requires changing them.

## UI String And Encoding Rules
- User-facing UI strings should default to Korean in this repository unless the task explicitly changes that policy.
- If string or encoding damage appears, restore execution first, then explicitly check for user-facing language regressions before finishing.
- If a broken string cannot be confidently reconstructed, replace it with a neutral Korean label instead of guessing the original wording.
- After string edits, verify `py_compile`, import, app creation, and visible UI labels together rather than treating them as separate concerns.

## Large File Safety Rules
- Do not use line-number-based overwrite edits on large files such as `gui_app.py`.
- Use context-based patches only when editing large files.
- Before editing a high-risk large file, create a timestamped backup or keep a known-good baseline copy.
- After any risky large-file edit, run `py_compile`, import, and app creation checks before making the next change.
- Do not mix string/encoding repair and feature work in the same edit sequence.
- If file size drops unexpectedly, key classes/functions disappear, or the main structure looks damaged, stop immediately and report the damage instead of continuing.

## High-Risk Edit Verification Rules
- Run an immediate integrity check after large-file edits.
- Do not report "fixed" or "completed" until post-edit verification has actually passed.
- When a known-good recovery baseline exists, recover from that baseline instead of guessing from a damaged file fragment.

## Reporting format
Use this structure unless the user asks otherwise:

[1] Changed files  
[2] What was changed  
[3] Why it was changed  
[4] Verification performed  
[5] Remaining risks or unverified items

## Coordination rule
- Use `CODEX.md` for repository-specific architecture, overlay/timeline, subtitle, preview, render, and performance preservation rules.
- If `AGENTS.md` and `CODEX.md` ever seem to conflict, prefer the stricter interpretation and call out the uncertainty explicitly.
