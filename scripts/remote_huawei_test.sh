#!/usr/bin/env bash
# Confirm Huawei SWR throughput using images never pulled before on this host.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
BASE=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library
test_one() {
  img=$1
  start=$(date +%s)
  if timeout 300 docker pull -q "$img" >/dev/null 2>&1; then
    end=$(date +%s)
    size=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
    mb=$((size/1024/1024)); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
    printf '%-28s OK %4dMB/%4ds ~%d MB/s\n' "${img##*/}" "$mb" "$elapsed" "$((mb/elapsed))"
  else
    printf '%-28s FAIL\n' "${img##*/}"
  fi
  docker rmi "$img" >/dev/null 2>&1 || true
}
test_one "$BASE/nginx:1.25-alpine"
test_one "$BASE/postgres:15-alpine"
test_one "$BASE/httpd:2.4-alpine"
test_one "$BASE/python:3.10-slim"
REMOTE
