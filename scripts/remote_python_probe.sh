#!/usr/bin/env bash
# Check which Python tooling already exists on the server (read-only).
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
echo "=== interpreters ==="
for c in python3 python3.10 python3.11 python3.12 conda mamba uv pip3; do
  p=$(command -v "$c" 2>/dev/null || true)
  printf '%-12s %s\n' "$c" "${p:-missing}"
done
echo "=== pip module ==="
python3 -m pip --version 2>&1 | head -2 || echo "no pip module"
echo "=== virtualenv module ==="
python3 -c 'import virtualenv; print("virtualenv", virtualenv.__version__)' 2>&1 | head -2 || true
echo "=== ensurepip ==="
python3 -c 'import ensurepip; print("ensurepip ok")' 2>&1 | head -2 || true
REMOTE
