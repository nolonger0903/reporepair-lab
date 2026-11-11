#!/usr/bin/env bash
# Create an isolated venv under /root/paperArts/bench using uv (no system changes).
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /root/paperArts/bench
INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

if [ ! -x venv/bin/python ]; then
  rm -rf venv
  uv venv venv --python 3.10
fi

uv pip install --python venv/bin/python --index-url "$INDEX" -e reporepair-lab pytest

echo "=== versions ==="
venv/bin/python -c "import sys, reporepair, minisweagent; print('python', sys.version.split()[0]); print('reporepair', reporepair.__version__); print('mini-swe-agent', minisweagent.__version__)"

echo "=== unit tests ==="
cd reporepair-lab
../venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
REMOTE
