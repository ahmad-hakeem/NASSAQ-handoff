#!/bin/bash
set -e

cd /home/runner/workspace

if [ -f frontend/package.json ]; then
  cd frontend
  npm install --legacy-peer-deps < /dev/null
  cd ..
fi

if [ -f backend/requirements.txt ]; then
  cd backend
  pip install -q -r requirements.txt < /dev/null 2>&1 || true
  cd ..
fi
