# Transcript JSON exchange

`transcript_exchange.py` provides a standard-library-only interchange format that preserves the segment and word timestamps produced by VibeCoding_VideoAnalyzer.

It is intentionally separate from the GUI, playback, and word-highlight paths. Existing application behavior is unchanged.

## Schema

```json
{
  "schema": "vibe-video-analyzer/transcript",
  "schemaVersion": 1,
  "createdAt": "2026-08-16T00:00:00Z",
  "media": {
    "path": "/Users/me/Movies/interview.mov",
    "fileName": "interview.mov",
    "durationSeconds": 120.5
  },
  "engine": {
    "application": "VibeCoding_VideoAnalyzer",
    "modelId": "large-v3-turbo",
    "language": "ko",
    "wordTimestamps": true
  },
  "segments": [
    {
      "id": "segment-1",
      "startSeconds": 1.25,
      "endSeconds": 2.5,
      "durationSeconds": 1.25,
      "text": "안녕하세요",
      "words": [
        {
          "text": "안녕",
          "startSeconds": 1.25,
          "endSeconds": 1.8
        }
      ]
    }
  ],
  "summary": {
    "segmentCount": 1,
    "wordCount": 1
  }
}
```

The exporter accepts the existing `TranscriptSegment(s, e, t, words)` and `TranscriptWord(word, s, e)` data classes as well as their legacy dictionary equivalents.

## Headless transcription

The CLI uses the existing `HyperTranscriptionEngine` but does not launch Tkinter or VLC.

```bash
python transcribe_cli.py "/Users/me/Movies/interview.mov" \
  --language ko \
  --model large-v3-turbo \
  --silero-vad \
  --whisperx-align \
  --output "/Users/me/Desktop/interview.vibe-transcript.json"
```

`--whisperx-align` requires the optional WhisperX dependency. Without it, Faster-Whisper or the existing MPS backend still emits word timestamps when supported.

Useful options:

```text
--device auto
--beam-size 5
--min-silence-ms 2000
--speech-pad-ms 250
--vad-threshold 0.35
--denoise
--dominant-speaker
--whisper-vad
--silero-vad
--whisperx-align
--remove-punctuation
--overwrite
```

Existing output is preserved unless `--overwrite` is explicit.

## Runtime boundary

The exchange module and its tests do not require media dependencies. Actual transcription still requires the same runtime as the main application, including the configured Whisper model, FFmpeg tooling, NumPy/Torch stack, and optional WhisperX/VAD packages.

The repository currently has no dependency manifest and the macOS runtime remains unverified until the project environment and models are restored.

## Apple Pro Video MCP handoff

The generated JSON is designed to be consumed without losing word timing:

```text
VibeCoding_VideoAnalyzer
  → *.vibe-transcript.json
  → Apple Pro Video MCP vibe_transcript_import
  → highlight_rank
  → edit_plan_build
      ├─ fcpxml_create_project
      └─ subtitle_segment → subtitle_write_srt
```

The analyzer supplies transcription and timestamps. Candidate quality ratings and actual Final Cut Pro compatibility remain separate evidence layers.

## Tests

The lightweight suite verifies normalization, schema round trips, protected writes, ordering validation, and that CLI help works without importing heavy runtime dependencies.

```bash
python -m unittest -v test_transcript_exchange.py
```
