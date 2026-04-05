#!/bin/bash
set -e

echo "=========================================="
echo "NASSAQ Build & Deployment"
echo "=========================================="

echo "Installing backend dependencies..."
cd /home/runner/workspace/backend
pip install -r requirements.txt --no-cache-dir -q 2>&1 | tail -3

echo "Building frontend..."
cd /home/runner/workspace/frontend
npm install --production --ignore-scripts 2>&1 | tail -3
npm run build 2>&1 | tail -3

echo "Cleaning up to reduce image size..."
cd /home/runner/workspace

rm -rf frontend/node_modules
rm -rf frontend/src
rm -rf .cache/pip .cache/uv .cache/huggingface
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find .pythonlibs -name '*.pyc' -delete 2>/dev/null || true
find .pythonlibs -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true
find .pythonlibs -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "Build complete."
echo "=========================================="
