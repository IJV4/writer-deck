#!/usr/bin/env bash
# Writer Deck — dev environment setup for WSL / Ubuntu desktop
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=== Writer Deck Dev Setup ==="

# 1. System packages
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-dev python3-venv python3-pip \
    libfreetype6-dev libjpeg-dev libopenjp2-7-dev \
    fonts-hack-ttf

# 2. Python venv + dev dependencies
echo "[2/4] Creating venv and installing Python packages..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements-dev.txt" -q

# 3. Create data directories
echo "[3/4] Creating data directories..."
mkdir -p ~/Documents/writer-deck
mkdir -p ~/.config/writer-deck

# 4. Verify
echo "[4/4] Verifying install..."
"$VENV_DIR/bin/python" -c "import PIL, yaml, pygame; print('  PIL, PyYAML, pygame OK')"

echo ""
echo "=== Dev setup complete! ==="
echo "  Activate: source venv/bin/activate"
echo "  Run tests: pytest"
echo "  Run app:   python main.py  (NullDriver + pygame emulator)"
echo "  PNG frames saved to /tmp/writer-deck/ when using NullDriver"
