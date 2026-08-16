# VibeCoding_VideoAnalyzer

Local video transcription and subtitle editing app built with Tkinter, VLC, Faster-Whisper, VAD, and FFmpeg-based tooling.

## Entry Points
- App entry: `main.py`
- Main UI: `gui_app.py`
- Playback wrapper: `video_player.py`
- Transcription engine: `engine_core.py`
- Timeline state: `timeline_manager.py`
- Headless transcript export: `transcribe_cli.py`
- Transcript interchange: `transcript_exchange.py`

## Timestamp-Preserving JSON Export

The analyzer already produces `TranscriptSegment(s, e, t, words)` values with word-level `TranscriptWord(word, s, e)` timing. The new isolated exchange path preserves that data in a versioned JSON document without changing the GUI, playback, or word-highlight behavior.

```bash
python transcribe_cli.py "/Users/me/Movies/interview.mov" \
  --language ko \
  --silero-vad \
  --output "/Users/me/Desktop/interview.vibe-transcript.json"
```

Optional precise alignment:

```bash
python transcribe_cli.py input.mov --whisperx-align
```

This requires the existing runtime dependencies and optional WhisperX package. Existing JSON output is preserved unless `--overwrite` is explicit.

The JSON can be handed to Apple Pro Video MCP without losing word timing:

```text
Vibe transcript JSON
  → vibe_transcript_import
  → highlight_rank
  → edit_plan_build
  → FCPXML + SRT
```

See [`docs/TRANSCRIPT_EXCHANGE.md`](docs/TRANSCRIPT_EXCHANGE.md) for the schema, options, and validation boundary.

Lightweight exchange tests do not import VLC, Torch, or Whisper:

```bash
python -m unittest -v test_transcript_exchange.py
```

## Current Platform Status
- Windows packaging flow exists via `build_release.bat` and `VibeAnalyzer.spec`.
- macOS compatibility work has started and the VLC embed path is now platform-aware.
- macOS runtime is not yet fully verified because the current machine is missing the project Python environment and required packages.

## macOS Runtime Check Status
Verified on 2026-03-20 in this workspace:
- `python3` is available: `Python 3.9.6`
- `.venv` is missing
- dependency manifest such as `requirements.txt` or `pyproject.toml` is missing
- `models/` directory is missing
- import checks currently fail for: `vlc`, `numpy`, `torch`, `faster_whisper`, `imageio_ffmpeg`, `transformers`, `silero_vad`, `noisereduce`, `PIL`
- `tkinter` import succeeds, but GUI window launch was not verifiable in this sandbox

## macOS Bring-Up Checklist
1. Create a local virtual environment.
2. Install the project dependencies into that environment.
3. Install VLC on macOS and confirm the Python `vlc` package can find the VLC runtime.
4. Restore or download the local speech models into `models/` if local bundled models are expected.
5. Run `python main.py` from the project root.
6. Verify video preview, subtitle preview, analysis start, and export paths.
7. Run `python transcribe_cli.py --help`, then produce one `.vibe-transcript.json` fixture from a short clip.

## Recommended macOS Smoke Test
1. Launch the app from the project root.
2. Select a short local `.mp4` file.
3. Confirm the splash screen appears and the main window opens.
4. Confirm video playback renders inside the app window.
5. Start a basic transcription run using CPU mode.
6. Confirm subtitle rows populate and preview subtitles appear in VLC playback.
7. Export `SRT` and confirm the file is created correctly.
8. Run the headless CLI on the same clip and confirm segment/word timestamps exist in the JSON.

## Notes
- `build_release.bat` is Windows-only.
- `VibeAnalyzer.spec` now exists again, but packaging should be re-validated later on an actual build machine.
- See `DEPLOYMENT.md` for packaging notes and `HANDOFF.md` for current project context.
