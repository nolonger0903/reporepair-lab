#!/usr/bin/env bash
# Throughput test with a DIFFERENT image per mirror so no layers are reused.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
test_one() {
  img=$1
  start=$(date +%s)
  if timeout 120 docker pull -q "$img" >/dev/null 2>&1; then
    end=$(date +%s); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
    size=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
    mb=$((size/1024/1024)); rate=$((mb/elapsed))
    printf '%-58s OK   %4dMB / %3ds  ~%d MB/s\n' "$img" "$mb" "$elapsed" "$rate"
  else
    printf '%-58s FAIL/TIMEOUT\n' "$img"
  fi
  docker rmi "$img" >/dev/null 2>&1 || true
}
test_one docker.1ms.run/library/alpine:3.19
test_one docker.m.daocloud.io/library/busybox:1.36
test_one dockerproxy.net/library/debian:bookworm-slim
test_one docker.1ms.run/library/ubuntu:22.04
test_one docker.m.daocloud.io/library/redis:7-alpine
REMOTE
