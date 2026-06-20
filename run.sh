#!/usr/bin/env bash
# -------------------------------------------------------
# run.sh — Start the BigQuery Release Notes Flask server
# -------------------------------------------------------
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"

# Activate virtual environment if it exists, else create one
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "🚀 Starting BigQuery Release Notes server..."
echo "   → http://localhost:5000"
echo "   Press Ctrl+C to stop."
echo ""

python app.py
