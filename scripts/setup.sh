#!/usr/bin/env bash
set -e

echo "========================================"
echo "     Nonull — Universal Domain AI Agent"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 not found. Install Python 3.10+:"
    echo "  apt install python3.12 python3.12-venv  (Ubuntu/Debian)"
    echo "  brew install python@3.12                (macOS)"
    exit 1
fi
echo "[OK] Python $(python3 --version | cut -d' ' -f2)"

# Create venv
if [ ! -d "venv" ]; then
    echo "[..] Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

echo "[..] Installing Nonull..."
pip install -e ".[dev,web]" -q
echo "[OK] Installed"

echo ""
echo "Setup complete!"
echo ""
echo "  nonull              Start CLI"
echo "  nonull-web          Start Web UI (localhost:8765)"
echo "  pytest tests/ -v    Run tests"
echo "  Edit .env to set LLM API key"
