#!/bin/bash
set -e

echo "=========================================="
echo "NASSAQ Build & Deployment"
echo "=========================================="

echo "Installing backend dependencies..."
cd /home/runner/workspace/backend
pip install -r requirements.txt --no-cache-dir --break-system-packages -q 2>&1 | tail -5

echo "Cleaning up to reduce image size..."
cd /home/runner/workspace

rm -rf frontend/node_modules
rm -rf frontend/src
rm -rf attached_assets
rm -rf test_reports
rm -rf memory
rm -rf .cache/pip .cache/uv .cache/huggingface .cache/typescript
rm -rf .git/lfs/objects
rm -rf .local/share .local/state
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find .pythonlibs -name '*.pyc' -delete 2>/dev/null || true
find .pythonlibs -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true
find .pythonlibs -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true
pip cache purge 2>/dev/null || true

echo ""
echo "Build complete. Frontend served from pre-built /frontend/build/"
echo "=========================================="
