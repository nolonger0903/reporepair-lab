#!/usr/bin/env bash
# Stop our collector and any stalled pull, then clean up images we pulled.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
echo "=== stopping collector ==="
pkill -f "scripts/collect.py" 2>/dev/null && echo "collector killed" || echo "collector not running"
pkill -f "docker pull" 2>/dev/null && echo "pull killed" || echo "pull not running"
sleep 1
echo "=== remaining processes ==="
ps -eo pid,etime,cmd | grep -E "[c]ollect.py|[d]ocker pull" || echo "(none)"
echo "=== our containers ==="
docker ps --format '{{.Names}}' | grep -c minisweagent || true
echo "=== removing images we pulled ==="
for img in swebench/sweb.eval.x86_64.pallets_1776_flask-5063 swebench/sweb.eval.x86_64.pallets_1776_flask-4045; do
  if docker images -q "$img" | grep -q .; then
    docker rmi "$img" 2>&1 | tail -2
  else
    echo "$img: not present"
  fi
done
echo "=== after ==="
docker images --format '{{.Repository}}' | grep sweb.eval || echo "no sweb images"
df -h / | tail -1
REMOTE
