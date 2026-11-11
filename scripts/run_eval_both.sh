#!/usr/bin/env bash
# Phase 6: evaluate base and SFT adapters on the held-out set, one rollout each.
set -eu
source ~/venvs/rrl/bin/activate
PROJECT="/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"
export MSWEA_COST_TRACKING=ignore_errors
export OPENAI_API_BASE=http://127.0.0.1:8000/v1
export OPENAI_API_KEY=dummy

# Docker churn can invalidate a cwd on /mnt/c; re-enter it before every run and
# pass absolute paths so pathlib never resolves against a dead directory.
run_one() {
    local model="$1" out="$2"
    cd /
    cd "$PROJECT"
    python "$PROJECT/scripts/evaluate.py" \
        --split "$PROJECT/data/taskset/eval_verified.jsonl" \
        --model "openai/$model" \
        --out "$PROJECT/data/eval_results/$out" \
        --rollouts 1 --steps 40
}

run_one base base
run_one sft sft
