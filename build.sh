#!/bin/bash
set -e
set -o pipefail

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
rm -rf build
npm install --legacy-peer-deps
unset DANGEROUSLY_DISABLE_HOST_CHECK
# craco.config.js calls dotenv.config(), which would re-inject the dev-only
# DANGEROUSLY_DISABLE_HOST_CHECK=true from frontend/.env and trip the
# production guard. Strip it from .env for the deploy build (ephemeral env).
if [ -f .env ]; then
  sed -i '/^DANGEROUSLY_DISABLE_HOST_CHECK=/d' .env
fi
GENERATE_SOURCEMAP=false DISABLE_ESLINT_PLUGIN=true npx craco build
test -f build/index.html || { echo "FATAL: frontend build did not produce build/index.html"; exit 1; }

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
