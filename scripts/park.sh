#!/usr/bin/env bash
set -e

cd /workspaces/training-coach-app

./scripts/dev-stop.sh

echo
echo "Stopping Codespace..."

if [ -n "${CODESPACE_NAME:-}" ]; then
  gh codespace stop -c "$CODESPACE_NAME"
else
  gh codespace stop
fi
