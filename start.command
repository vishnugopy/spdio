#!/bin/bash
cd "$(dirname "$0")"

echo "======================================"
echo "  Spdio"
echo "======================================"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python is not installed on this Mac."
  echo "Please install it from https://www.python.org/downloads/ then double-click this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi

python3 install_deps.py || { read -r -p "Press Enter to close..."; exit 1; }

if [ ! -d "venv" ]; then
  echo "Setup did not complete. Press Enter to close..."
  read -r -p ""
  exit 1
fi

source venv/bin/activate
python app.py
