#!/usr/bin/env bash
# Launch collection inside a detached tmux session (survives tool timeouts).
# Usage: launch_collect.sh <split> <rollouts> [logname]
set -euo pipefail
cd "/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"
mkdir -p data

SPLIT=${1:?split file required}
ROLLOUTS=${2:-3}
LOG=${3:-pilot}

tmux kill-session -t rrl 2>/dev/null || true
tmux new-session -d -s rrl \
  "bash scripts/local_collect.sh --split $SPLIT --rollouts $ROLLOUTS --steps 40 --out data/trajectories > data/$LOG.log 2>&1"

sleep 2
tmux ls
echo "--- log ---"
tail -5 "data/$LOG.log" 2>/dev/null || echo "(no log yet)"
