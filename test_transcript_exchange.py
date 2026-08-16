import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from config_models import TranscriptSegment, TranscriptWord
from transcript_exchange import (
    SCHEMA_ID,
    TranscriptExchangeError,
    build_transcript_document,
    load_transcript_json,
    write_transcript_json,
)


class TranscriptExchangeTests(unittest.TestCase):
    def sample_segments(self):
        return [
            TranscriptSegment(
                s=1.25,
                e=2.5,
                t="안녕하세요",
                words=[
                    TranscriptWord(word="안녕", s=1.25, e=1.8),
                    TranscriptWord(word="하세요", s=1.81, e=2.5),
                ],
            ),
            {
                "s": 3.0,
                "e": 4.25,
                "t": "두 번째 문장",
                "words": [
                    {"word": "두", "s": 3.0, "e": 3.2},
                    {"word": "번째", "s": 3.21, "e": 3.6},
                    {"word": "문장", "s": 3.61, "e": 4.25},
                ],
            },
        ]

    def test_builds_versioned_document_with_word_timestamps(self):
        document = build_transcript_document(
            "/tmp/interview.mov",
            self.sample_segments(),
            duration_seconds=10,
            engine={"modelId": "large-v3-turbo", "language": "ko"},
            created_at="2026-08-16T00:00:00Z",
        )
        self.assertEqual(document["schema"], SCHEMA_ID)
        self.assertEqual(document["schemaVersion"], 1)
        self.assertEqual(document["summary"], {"segmentCount": 2, "wordCount": 5})
        self.assertEqual(document["segments"][0]["words"][1], {
            "text": "하세요",
            "startSeconds": 1.81,
            "endSeconds": 2.5,
        })

    def test_round_trip_preserves_existing_output_by_default(self):
        document = build_transcript_document(
            "/tmp/interview.mov",
            self.sample_segments(),
            duration_seconds=10,
            created_at="2026-08-16T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "interview.vibe-transcript.json"
            written = write_transcript_json(str(output), document)
            self.assertEqual(Path(written), output.resolve())
            loaded = load_transcript_json(str(output))
            self.assertEqual(loaded["summary"]["wordCount"], 5)
            with self.assertRaisesRegex(TranscriptExchangeError, "already exists"):
                write_transcript_json(str(output), document)

            document["segments"][0]["text"] = "수정된 문장"
            write_transcript_json(str(output), document, overwrite=True)
            with output.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self.assertEqual(raw["segments"][0]["text"], "수정된 문장")

    def test_rejects_unsorted_words(self):
        segments = [{
            "s": 0,
            "e": 2,
            "t": "bad order",
            "words": [
                {"word": "later", "s": 1, "e": 1.5},
                {"word": "earlier", "s": 0.2, "e": 0.8},
            ],
        }]
        with self.assertRaisesRegex(TranscriptExchangeError, "sorted"):
            build_transcript_document("/tmp/input.mov", segments)

    def test_cli_help_does_not_require_heavy_runtime_dependencies(self):
        project_root = Path(__file__).resolve().parent
        completed = subprocess.run(
            [sys.executable, str(project_root / "transcribe_cli.py"), "--help"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("vibe-transcript.json", completed.stdout)


if __name__ == "__main__":
    unittest.main()
