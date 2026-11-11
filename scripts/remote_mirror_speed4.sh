#!/usr/bin/env bash
# Try additional registry mirrors with unique images (no layer-cache reuse).
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
  if timeout 90 docker pull -q "$img" >/dev/null 2>&1; then
    end=$(date +%s)
    size=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
    mb=$((size/1024/1024)); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
    printf '%-70s OK %4dMB/%3ds ~%d MB/s\n' "$img" "$mb" "$elapsed" "$((mb/elapsed))"
  else
    printf '%-70s FAIL\n' "$img"
  fi
  docker rmi "$img" >/dev/null 2>&1 || true
}
test_one swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/debian:bookworm-slim
test_one docker.aityp.com/library/alpine:3.18
test_one docker.fnnas.com/library/busybox:1.35
test_one docker.amingg.com/library/alpine:3.17
test_one docker.hub.rfc1918.cc/library/debian:bullseye-slim
test_one docker.1panel.live/library/alpine:3.16
REMOTE
