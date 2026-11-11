#!/usr/bin/env bash
# Verify that image pulls actually work, using a tiny image. Cleans up after itself.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$HOST" 'bash -s' <<'REMOTE'
echo "=== plain pull (uses configured mirrors) ==="
if timeout 60 docker pull hello-world 2>&1 | tail -3; then echo "PULL_OK"; else echo "PULL_FAILED"; fi
echo "=== explicit mirror pull ==="
if timeout 90 docker pull docker.m.daocloud.io/library/hello-world:latest 2>&1 | tail -3; then echo "MIRROR_OK"; else echo "MIRROR_FAILED"; fi
echo "=== cleanup probe images ==="
docker rmi hello-world >/dev/null 2>&1 || true
docker rmi docker.m.daocloud.io/library/hello-world:latest >/dev/null 2>&1 || true
echo "cleanup done"
REMOTE
