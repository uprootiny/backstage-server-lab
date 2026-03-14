#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-}"
TARGET_DIR="${2:-/workspace/backstage-server-lab}"

if [[ -z "$REPO_URL" ]]; then
  echo "usage: $0 <repo_url> [target_dir]"
  exit 2
fi

if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "repo already exists: $TARGET_DIR"
else
  git clone "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"
bash scripts/bootstrap.sh
bash scripts/up.sh
bash scripts/sanity.sh

echo "vast_clone_bootstrap_complete target=$TARGET_DIR"
