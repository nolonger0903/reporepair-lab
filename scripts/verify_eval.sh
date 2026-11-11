#!/usr/bin/env bash
# Verify the eval task set end to end. Requires all images to be present.
# Paths are resolved inside Python (absolute, from the repo root), so no --out here.
set -euo pipefail
source ~/venvs/rrl/bin/activate
exec python "/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab/scripts/verify_taskset.py"
