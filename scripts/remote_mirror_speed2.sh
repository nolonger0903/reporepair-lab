#!/usr/bin/env bash
# Throughput test across more Docker Hub mirrors (small image, cleaned up after).
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
IMAGES="
docker.1ms.run/library/python:3.12-slim
docker.m.daocloud.io/library/python:3.12-slim
docker.1panel.top/library/python:3.12-slim
docker.unsee.tech/library/python:3.12-slim
docker.anye.xyz/library/python:3.12-slim
docker.nju.edu.cn/library/python:3.12-slim
mirror.azure.cn/docker-hub/library/python:3.12-slim
dockerproxy.net/library/python:3.12-slim
"
for img in $IMAGES; do
  start=$(date +%s)
  if timeout 90 docker pull -q "$img" >/dev/null 2>&1; then
    end=$(date +%s); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
    size=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
    mb=$((size/1024/1024)); rate=$((mb/elapsed))
    printf '%-58s OK   %4dMB / %3ds  ~%d MB/s\n' "$img" "$mb" "$elapsed" "$rate"
  else
    printf '%-58s FAIL\n' "$img"
  fi
  docker rmi "$img" >/dev/null 2>&1 || true
done
REMOTE
