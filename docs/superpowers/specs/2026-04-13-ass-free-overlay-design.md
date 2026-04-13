# ASS-Free Overlay Design

## Goal

Remove ASS as the runtime subtitle representation and make preview, export, and burn work from one shared subtitle cue pipeline.

## Decision

We will use a shared `SubtitleCue` model as the single source of truth for subtitle timing and text. Preview will render cues directly, export will serialize cues directly, and burn will render cues through FFmpeg `drawtext` instead of ASS.

## Scope

- Replace ASS preview generation with direct overlay logic.
- Replace ASS burn generation with FFmpeg `drawtext` filter generation.
- Keep text exports (`SRT`, `VTT`, `TXT`, `CSV`) but make them use shared cues.
- Preserve current timing rules: no overlap, edited segment times are authoritative.

## Non-Goals

- Rebuild preview to match full ASS fidelity.
- Add draggable overlay editing in this pass.
- Change transcription or timeline editing behavior.

## Architecture

### Cue engine

Introduce a small subtitle module that converts `results_data` rows into normalized `SubtitleCue` instances. This module owns:

- timing normalization
- overlap trimming
- text cleanup
- style packaging for render/export

### Preview

Preview continues to use direct overlay on the player, but it now reads shared cues instead of building a parallel ASS-specific path.

### Export

All subtitle text exports read shared cues and format from those values only.

### Burn

Burn uses FFmpeg `drawtext` with one filter chain generated from shared cues plus style settings. Cue text is written to temporary text files to avoid filter escaping issues.

## Risks

- `drawtext` style fidelity is lower than ASS in edge cases.
- Font resolution may vary by machine if the requested font is unavailable to FFmpeg.
- Very large cue counts can make filter chains long.

## Success Criteria

- Preview works without generating preview ASS files.
- Burn works without generating export/burn ASS files.
- SRT/VTT/TXT/CSV export matches editor timing.
- Edited timing in the UI matches preview and burn timing.
