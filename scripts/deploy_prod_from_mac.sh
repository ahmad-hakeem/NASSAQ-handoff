#!/usr/bin/env bash
# ==============================================================================
# Build & Deploy to Production Directly From Local Mac (linux/amd64)
# Usage: ./scripts/deploy_uat_from_mac.sh [TAG]
# Example: ./scripts/deploy_uat_from_mac.sh v1.0.0
# ==============================================================================

set -e

TAG="${1:-1.1.1}"
REGISTRY="registry.nassaqapp.com"
PROJECT="nassaq"
IMAGE_NAME="nassaq-app"

FULL_IMAGE="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:latest"

export PATH=$PATH:/usr/local/bin:/opt/homebrew/bin

echo "🚀 Building NASSAQ Production image for linux/amd64 locally on Mac (Tag: ${TAG})..."

docker build --platform linux/amd64 -t "${FULL_IMAGE}" -t "${LATEST_IMAGE}" .

echo "🔐 Logging in to Harbor Registry..."
docker login "${REGISTRY}" -u admin -p Nassaq2026

echo "⬆️ Pushing images to ${REGISTRY}..."
docker push "${FULL_IMAGE}"
docker push "${LATEST_IMAGE}"

echo "⛵ Triggering Kubernetes Rollout Restart in production-nassaq..."
ssh root@2.24.0.169 "kubectl set image deployment/nassaq-app nassaq-app=${FULL_IMAGE} -n production-nassaq && kubectl rollout restart deployment/nassaq-app -n production-nassaq && kubectl rollout status deployment/nassaq-app -n production-nassaq --timeout=180s"

echo "✅ Deployment to Production finished successfully!"
