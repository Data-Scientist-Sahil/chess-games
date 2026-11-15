#!/usr/bin/env bash
# setup.sh — one-time setup for the chess MCP server on macOS.
# Installs Stockfish (the correct build for YOUR Mac) and the Python deps.
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Installing Stockfish via Homebrew (the right arch for this Mac)..."
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install it from https://brew.sh, then re-run this script."
  exit 1
fi
brew list stockfish >/dev/null 2>&1 || brew install stockfish
echo "    stockfish -> $(command -v stockfish)"

echo "==> Creating a Python virtual environment in ./venv ..."
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo
echo "==> Done."
echo "    MCP server interpreter : $(pwd)/venv/bin/python"
echo "    MCP server script      : $(pwd)/chess_mcp.py"
echo
echo "Next: add this server to Claude Desktop's config, then restart the app."
echo "See claude_desktop_config.example.json in this folder, and the README."
echo
echo "To test the engine harness (the exact thing used for the 4-game ladder):"
echo "    source venv/bin/activate"
echo "    python engine_game.py new demo 1500"
echo "    python engine_game.py mymove demo e4"
