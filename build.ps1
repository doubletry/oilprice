param(
    [string]$OutputName = "oilprice.exe"
)

$ErrorActionPreference = "Stop"

poetry run python -m nuitka `
  --onefile `
  --output-dir=dist `
  --output-filename=$OutputName `
  --assume-yes-for-downloads `
  ./src/main.py
