#!/bin/zsh
set -e

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: .venv/bin/python not found."
  echo "Create the macOS virtual environment first."
  exit 1
fi

exec .venv/bin/python main.py
