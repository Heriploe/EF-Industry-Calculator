#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "PyInstaller not found, installing..."
  python3 -m pip install --user pyinstaller
fi

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name interactive_decompose_app \
  --add-data "Product:Product" \
  --add-data "Printer:Printer" \
  --add-data "Refinery:Refinery" \
  --add-data "Inventory:Inventory" \
  --add-data "types.json:." \
  --add-data "industry_blueprints.json:." \
  interactive_decompose_app.py

echo "Build complete: $ROOT_DIR/dist/interactive_decompose_app"
