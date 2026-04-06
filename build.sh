#!/bin/bash
set -e

echo "=========================================="
echo "NASSAQ Build & Deployment"
echo "=========================================="

echo "Setting up Python virtual environment..."
cd /home/runner/workspace
python3 -m venv /home/runner/workspace/.venv || true
source /home/runner/workspace/.venv/bin/activate

echo "Installing backend dependencies..."
cd /home/runner/workspace/backend
pip install -r requirements.txt --no-cache-dir -q 2>&1 | tail -5

echo "Building frontend..."
cd /home/runner/workspace/frontend
npm install --legacy-peer-deps 2>&1 | tail -5
GENERATE_SOURCEMAP=false npx craco build 2>&1 | tail -20

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
pip cache purge 2>/dev/null || true

echo ""
echo "Build complete."
echo "=========================================="
