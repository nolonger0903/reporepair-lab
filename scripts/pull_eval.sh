#!/usr/bin/env bash
# Pull the eval-candidate images locally (Docker Desktop).
set -euo pipefail
source ~/venvs/rrl/bin/activate
cd "/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"
exec python scripts/pull_split_images.py data/taskset/eval_candidates.jsonl
