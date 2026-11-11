#!/usr/bin/env bash
# Measure real pull throughput through each reachable mirror, then clean up.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
for m in docker.m.daocloud.io docker.1ms.run hub.rat.dev; do
  img="$m/library/python:3.12-slim"
  echo "--- $m ---"
  start=$(date +%s)
  if timeout 240 docker pull -q "$img" >/dev/null 2>&1; then
    end=$(date +%s)
    size=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
    elapsed=$((end - start))
    mb=$((size / 1024 / 1024))
    rate=$(( mb / (elapsed > 0 ? elapsed : 1) ))
    echo "OK: ${mb}MB in ${elapsed}s (~${rate} MB/s)"
  else
    echo "FAILED or timed out"
  fi
  docker rmi "$img" >/dev/null 2>&1 || true
done
REMOTE
