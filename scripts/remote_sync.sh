#!/usr/bin/env bash
# Sync the project to the training server. No --delete: never remove remote work.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}
SRC="/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab/"
DST=/root/paperArts/bench/reporepair-lab/

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
mkdir -p /root/paperArts/bench/reporepair-lab
echo "remote dir ready"
REMOTE

rsync -az \
  -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.egg-info' \
  --exclude 'data/trajectories' \
  --exclude 'refs' \
  --exclude '.venv-train' \
  --exclude 'outputs' \
  "$SRC" "$HOST:$DST"

echo "synced -> $HOST:$DST"
