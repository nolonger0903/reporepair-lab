#!/usr/bin/env bash
# Forward local 8000 -> the GPU server's vLLM port so the local agent can call it.
set -eu
# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}
exec ssh -i "$KEY" -N -o ServerAliveInterval=30 -L 8000:127.0.0.1:8000 "$HOST"
