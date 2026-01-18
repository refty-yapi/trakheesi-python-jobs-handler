#!/bin/bash
# Trakheesi Workers Installer for Mac/Linux

set -e

REPO="refty-yapi/trakheesi-python-jobs-handler"
INSTALL_DIR="$HOME/trakheesi-workers"

echo "=== Trakheesi Workers Installer ==="
echo ""

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Download and extract
echo "Downloading..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
curl -sL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$INSTALL_DIR" --strip-components=1

cd "$INSTALL_DIR"

# Install dependencies
echo "Installing dependencies..."
uv sync

# Install Playwright browsers
echo "Installing Chromium browser..."
uv run playwright install chromium

echo ""
echo "=== Installation complete! ==="
echo ""
echo "To run:"
echo "  cd $INSTALL_DIR"
echo "  uv run python master.py -n 5 --visible"
echo ""
