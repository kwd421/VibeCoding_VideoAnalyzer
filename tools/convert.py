import os
import subprocess
from pathlib import Path

models = [
    "seastar105/whisper-small-komixv2",
    "seastar105/whisper-medium-ko-zeroth",
    "o0dimplz0o/Whisper-Large-v3-turbo-STT-Zeroth-KO-v2"
]

ROOT_DIR = Path(__file__).resolve().parents[1]
converter_exe = str(ROOT_DIR / '.venv' / 'Scripts' / 'ct2-transformers-converter.exe')
os.makedirs(ROOT_DIR / 'models', exist_ok=True)

for m in models:
    out_dir = str(ROOT_DIR / 'models' / m.split('/')[-1])
    if os.path.exists(out_dir):
        print(f"Skipping {m}, already exists")
        continue

    cmd1 = [
        converter_exe,
        "--model", m,
        "--output_dir", out_dir,
        "--quantization", "int8",
        "--copy_files", "tokenizer.json", "preprocessor_config.json"
    ]

    cmd2 = [
        converter_exe,
        "--model", m,
        "--output_dir", out_dir,
        "--quantization", "int8"
    ]

    print(f"Converting {m} (with copy_files)...")
    res = subprocess.run(cmd1, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Retrying {m} without copy_files...")
        os.makedirs(out_dir, exist_ok=True)
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        if res2.returncode != 0:
            print(f"Error converting {m}:\n{res2.stderr}")
        else:
            print(f"Success {m} (no copy_files)")
    else:
        print(f"Success {m} (with copy_files)")

print("All done.")
