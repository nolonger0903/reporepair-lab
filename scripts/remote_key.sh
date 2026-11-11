#!/usr/bin/env bash
# Copy the DeepSeek API key to the server without printing it.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}
LOCAL_ENV="$HOME/.config/mini-swe-agent/.env"

if [ ! -f "$LOCAL_ENV" ]; then
  echo "local key file not found: $LOCAL_ENV" >&2
  exit 1
fi

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'mkdir -p /root/.config/mini-swe-agent && chmod 700 /root/.config/mini-swe-agent'
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new "$LOCAL_ENV" "$HOST:/root/.config/mini-swe-agent/.env"
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new "$LOCAL_ENV" "$HOST:/root/paperArts/bench/.env"

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
chmod 600 /root/.config/mini-swe-agent/.env /root/paperArts/bench/.env
cd /root/paperArts/bench
venv/bin/python - <<'PY'
import os
from pathlib import Path
for line in Path("/root/paperArts/bench/.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()
key = os.environ.get("DEEPSEEK_API_KEY", "")
print("key present:", bool(key), "| length:", len(key), "| prefix:", key[:3] + "..." if key else "-")
print("model:", os.environ.get("MSWEA_MODEL_NAME", "(unset)"))
PY
REMOTE
