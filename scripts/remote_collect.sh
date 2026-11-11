#!/usr/bin/env bash
# Run the collector on the training server. Pass extra args after the script name.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}
EXTRA="${*:-}"

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<REMOTE
set -euo pipefail
cd /root/paperArts/bench/reporepair-lab
set -a
. /root/paperArts/bench/.env
set +a
exec ../venv/bin/python scripts/collect.py $EXTRA
REMOTE
