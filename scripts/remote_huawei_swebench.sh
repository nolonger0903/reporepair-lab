#!/usr/bin/env bash
# Can Huawei SWR serve the SWE-bench namespace? Pull one real image, then clean up.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
MIRROR=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io
CANON=swebench/sweb.eval.x86_64.pallets_1776_flask-4045:latest
IMG="$MIRROR/$CANON"

start=$(date +%s)
if timeout 1200 docker pull -q "$IMG" >/dev/null 2>&1; then
  end=$(date +%s)
  size=$(docker image inspect "$IMG" --format '{{.Size}}' 2>/dev/null || echo 0)
  mb=$((size/1024/1024)); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
  echo "SUCCESS: ${mb}MB in ${elapsed}s (~$((mb/elapsed)) MB/s)"
  docker tag "$IMG" "$CANON" && echo "tagged as canonical name"
  docker rmi "$IMG" >/dev/null 2>&1 || true
  docker images --format '{{.Repository}}:{{.Tag}}' | grep sweb.eval || true
  docker rmi "$CANON" >/dev/null 2>&1 || true
  echo "cleaned up"
else
  echo "FAILED: Huawei mirror cannot serve $IMG"
fi
REMOTE
