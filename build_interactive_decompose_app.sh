#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# PyInstaller --add-data separator: ';' on Windows, ':' on POSIX
ADD_DATA_SEP=':'
case "${OS:-}" in
  Windows_NT) ADD_DATA_SEP=';' ;;
esac
case "$(uname -s 2>/dev/null || echo unknown)" in
  CYGWIN*|MINGW*|MSYS*) ADD_DATA_SEP=';' ;;
esac

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "PyInstaller not found, installing..."
  python3 -m pip install --user pyinstaller
fi

python3 -m PyInstaller   --noconfirm   --clean   --windowed   --name interactive_decompose_app   --add-data "Product${ADD_DATA_SEP}Product"   --add-data "Printer${ADD_DATA_SEP}Printer"   --add-data "Refinery${ADD_DATA_SEP}Refinery"   --add-data "Inventory${ADD_DATA_SEP}Inventory"   --add-data "types.json${ADD_DATA_SEP}."   --add-data "industry_blueprints.json${ADD_DATA_SEP}."   interactive_decompose_app.py

echo "Build complete: $ROOT_DIR/dist/interactive_decompose_app"
