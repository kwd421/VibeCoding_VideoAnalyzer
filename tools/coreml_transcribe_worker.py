import argparse
import json
import os
import sys

import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.engine.engine_core import HyperTranscriptionEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", default=None)
    parser.add_argument("--word-timestamps", action="store_true")
    args = parser.parse_args()

    audio_chunk = np.load(args.input).astype(np.float32, copy=False)
    engine = HyperTranscriptionEngine()
    engine.set_model_id(args.model_id)
    try:
        segments = engine._transcribe_with_coreml_local(audio_chunk, args.language, args.word_timestamps)
        payload = [
            {
                "text": seg.text,
                "start": float(seg.start),
                "end": float(seg.end),
                "words": [
                    {
                        "word": w.word,
                        "start": float(w.start),
                        "end": float(w.end),
                    }
                    for w in (seg.words or [])
                ],
            }
            for seg in segments
        ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    finally:
        engine.release_runtime_memory()


if __name__ == "__main__":
    main()
