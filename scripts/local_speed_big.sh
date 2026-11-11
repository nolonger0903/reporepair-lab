#!/usr/bin/env bash
# Sustained local pull speed with a large image (small images are dominated by setup time).
set -uo pipefail
IMG=node:20
start=$(date +%s)
if timeout 900 docker pull -q "$IMG" >/dev/null 2>&1; then
  end=$(date +%s)
  size=$(docker image inspect "$IMG" --format '{{.Size}}' 2>/dev/null || echo 0)
  mb=$((size/1024/1024)); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
  echo "OK: ${mb}MB in ${elapsed}s (~$((mb/elapsed)) MB/s uncompressed)"
else
  echo "FAILED/TIMEOUT"
fi
docker rmi "$IMG" >/dev/null 2>&1 || true
