#!/bin/bash
set -e

# Resolve project root (directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate venv if present (check project root first, then parent dirs)
for VENV_DIR in "$SCRIPT_DIR/.venv" "$SCRIPT_DIR/../.venv" "$SCRIPT_DIR/../../.venv"; do
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        break
    fi
done

echo "=== Format check (black) ==="
black --check "$SCRIPT_DIR/backend/" "$SCRIPT_DIR/main.py"

echo ""
echo "=== Tests (pytest) ==="
cd "$SCRIPT_DIR/backend" && python -m pytest tests/ -v
