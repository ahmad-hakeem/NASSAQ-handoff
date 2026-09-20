#!/bin/bash
set -e
set -o pipefail

echo "=========================================="
echo "NASSAQ Build & Deployment"
echo "=========================================="

echo "Setting up Python virtual environment..."
cd /home/runner/workspace
python3 -m venv /home/runner/workspace/.venv
source /home/runner/workspace/.venv/bin/activate

echo "Installing backend dependencies..."
cd /home/runner/workspace/backend
# Install into the SAME interpreter used by the isolated startup probes.
# Workspace pip/PYTHONPATH settings must not redirect installs to .pythonlibs
# or make pip treat packages outside this environment as already installed.
# Keep package-index/security-registry settings intact.
unset PIP_TARGET PIP_PREFIX PIP_USER PYTHONPATH PYTHONHOME
python -I -m pip install --ignore-installed --no-user \
  -r requirements.txt --no-cache-dir -q

# Replit Publish owns production schema changes.  Keep this image build
# database-independent: it must not connect to PostgreSQL or execute DDL.

echo "Checking fresh-process backend imports (no database access)..."
python /home/runner/workspace/scripts/benchmark_backend_startup.py

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

# COLD-START: autoscale starts a fresh instance from the image on every
# scale-from-zero, and the backend's import graph is large. Without cached
# bytecode Python recompiles every module on that first request, which is the
# slowest part of the cold start (and can outlast an uptime probe's timeout).
# Precompiling here — after the __pycache__ purge above, so it is the LAST word
# — bakes the .pyc files into the image so every instance starts warm.
# The venv is already active from the top of this script; never re-source it
# here (a missing path would trip `set -e` and fail an otherwise good build).
echo "Precompiling Python bytecode (cold-start)..."
python -m compileall -q -j 0 /home/runner/workspace/backend >/dev/null 2>&1 || true
python -m compileall -q -j 0 /home/runner/workspace/.venv/lib >/dev/null 2>&1 || true
echo "Bytecode precompiled."

echo ""
echo "Build complete."
echo "=========================================="
