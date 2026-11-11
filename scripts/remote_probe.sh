#!/usr/bin/env bash
# Create the bench workspace and probe outbound network. No packages installed.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$HOST" 'bash -s' <<'REMOTE'
mkdir -p /root/paperArts/bench
echo "=== bench dir ==="
ls -ld /root/paperArts/bench
echo "=== network ==="
for url in https://api.deepseek.com https://pypi.org/simple/ https://pypi.tuna.tsinghua.edu.cn/simple/ https://registry-1.docker.io/v2/ https://hf-mirror.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$url" || echo "ERR")
  printf '%-45s %s\n' "$url" "$code"
done
echo "=== existing docker images (not ours, do not touch) ==="
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | head -10
echo "=== nvidia runtime ==="
docker info --format '{{json .Runtimes}}' 2>/dev/null | head -c 300; echo
REMOTE
