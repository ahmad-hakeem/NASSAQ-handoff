#!/usr/bin/env bash
# One-time setup, run by the repo owner: enables branch protection on main
# requiring the 4 CI jobs. Needs: GITHUB_TOKEN with repo admin on
# ahmadzalat44/NASSAQ_Jul_26. NOTE: required checks on a PRIVATE repo need
# GitHub Pro/Team (or make the repo public).
set -euo pipefail
: "${GITHUB_TOKEN:?export GITHUB_TOKEN=<personal access token with repo admin>}"
REPO="${1:-ahmadzalat44/NASSAQ_Jul_26}"

curl -sf -X PUT \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$REPO/branches/main/protection" \
  -d '{
    "required_status_checks": {"strict": true, "contexts": ["backend", "frontend", "e2e", "security"]},
    "enforce_admins": true,
    "required_pull_request_reviews": null,
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false
  }'
echo "Branch protection enabled on $REPO main"
