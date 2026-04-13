# ASS-Free Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ASS-based subtitle preview and burn with a shared cue engine and direct render paths.

**Architecture:** Add a focused subtitle cue module that builds normalized cues from transcript rows. Route preview, export, and burn through that cue layer so subtitle timing comes from one source of truth. Use VLC marquee for preview and FFmpeg `drawtext` for burn.

**Tech Stack:** Python, Tkinter, VLC, FFmpeg, unittest

---

### Task 1: Add subtitle cue engine

**Files:**
- Create: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/subtitle_cues.py`
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/tests/test_timing_and_split_rules.py`

- [ ] Add `SubtitleCue` and `SubtitleRenderStyle` dataclasses plus cue builder helpers.
- [ ] Add tests for overlap trimming and export formatting.

### Task 2: Route preview and export through cues

**Files:**
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/gui_app.py`
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/tests/test_timing_and_split_rules.py`

- [ ] Replace ASS-specific preview/export preparation with cue helpers.
- [ ] Keep direct live overlay preview and ensure edited segment timing is authoritative.
- [ ] Add regression tests for cue-driven preview/export behavior.

### Task 3: Replace ASS burn with drawtext burn

**Files:**
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/video_editor.py`
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/analysis_controller.py`
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/gui_app.py`
- Modify: `/Users/seinel/Projects/VibeCoding_VideoAnalyzer/tests/test_timing_and_split_rules.py`

- [ ] Pass subtitle burn payload instead of ASS path.
- [ ] Generate `drawtext` filter chains from cues and style.
- [ ] Add tests that verify burn payload generation and drawtext filter content.
