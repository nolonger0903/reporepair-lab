#!/usr/bin/env bash
# Find a reachable Docker Hub mirror on the server. Read-only.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$HOST" 'bash -s' <<'REMOTE'
echo "=== daemon config ==="
cat /etc/docker/daemon.json 2>/dev/null || echo "(no daemon.json)"
echo "=== proxy env ==="
env | grep -i proxy || echo "(none)"
echo "=== mirror reachability ==="
for host in docker.m.daocloud.io dockerproxy.com hub-mirror.c.163.com mirror.ccs.tencentyun.com docker.1panel.live dockerhub.icu; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$host/v2/" 2>/dev/null || echo ERR)
  printf '%-32s %s\n' "$host" "$code"
done
echo "=== direct host resolution ==="
getent hosts registry-1.docker.io || echo "no dns"
REMOTE
