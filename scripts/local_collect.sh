#!/usr/bin/env bash
# Run the collector on the local machine (Docker Desktop). Args are passed through.
set -euo pipefail
source ~/venvs/rrl/bin/activate
cd "/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"
set -a
. "$HOME/.config/mini-swe-agent/.env"
set +a
exec python scripts/collect.py "$@"
