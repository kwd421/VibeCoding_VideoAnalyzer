import os
import subprocess

models = [
    "seastar105/whisper-small-komixv2",
    "seastar105/whisper-medium-ko-zeroth",
    "o0dimplz0o/Whisper-Large-v3-turbo-STT-Zeroth-KO-v2"
]

converter_exe = r".\.venv\Scripts\ct2-transformers-converter.exe"
os.makedirs("models", exist_ok=True)

for m in models:
    out_dir = f"models/{m.split('/')[-1]}"
    if os.path.exists(out_dir):
        print(f"Skipping {m}, already exists")
        continue

    # 1. 시도: copy_files 포함
    cmd1 = [
        converter_exe,
        "--model", m,
        "--output_dir", out_dir,
        "--quantization", "int8",
        "--copy_files", "tokenizer.json", "preprocessor_config.json"
    ]
    
    # 2. 시도: copy_files 제외
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
        os.makedirs(out_dir, exist_ok=True) # it might fail after creating dir
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
