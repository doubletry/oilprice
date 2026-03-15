#!/bin/bash
set -e

OUTPUT_NAME="${1:-oilprice}"

poetry run python -m nuitka \
  --onefile \
  --output-dir=dist \
  --output-filename="$OUTPUT_NAME" \
  --assume-yes-for-downloads \
  ./src/main.py