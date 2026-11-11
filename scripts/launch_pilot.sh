#!/usr/bin/env bash
# Launch the pilot collection inside a detached tmux session (survives tool timeouts).
set -euo pipefail
cd "/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"
mkdir -p data

tmux kill-session -t rrl 2>/dev/null || true
tmux new-session -d -s rrl \
  "bash scripts/local_collect.sh --split data/taskset/pilot_seaborn.jsonl --rollouts 3 --steps 25 --out data/trajectories > data/pilot.log 2>&1"

sleep 2
tmux ls
echo "--- first log lines ---"
tail -5 data/pilot.log 2>/dev/null || echo "(log not created yet)"
