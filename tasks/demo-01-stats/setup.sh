#!/usr/bin/env bash
# Restore the demo fixture's git baseline (its nested .git is not tracked).
set -euo pipefail
cd "$(dirname "$0")/repo"
if [ ! -d .git ]; then
  git init -q
  git add -A
  git commit -qm "buggy baseline"
  echo "baseline restored for demo-01-stats"
else
  echo "demo-01-stats repo already initialized"
fi
