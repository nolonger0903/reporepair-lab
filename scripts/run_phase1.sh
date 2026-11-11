#!/usr/bin/env bash
# Phase 1: 用 mini-swe-agent 在 demo-01-stats 上跑一次完整修复
set -euo pipefail
source ~/venvs/rrl/bin/activate

ROOT="/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"
TASK_TEXT="$(cat "$ROOT/tasks/demo-01-stats/task.md")"

cd "$ROOT"
exec mini \
  -c mini.yaml \
  -c "$ROOT/configs/phase1-deepseek.yaml" \
  --task "$TASK_TEXT" \
  --output "$ROOT/data/phase1-demo-01.traj.json" \
  -y
