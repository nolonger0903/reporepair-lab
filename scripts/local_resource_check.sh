#!/usr/bin/env bash
# Local resource snapshot + pull speed sample (small unique image, removed after).
set -uo pipefail
echo "=== C: free ==="
df -h /mnt/c 2>/dev/null | tail -1 || echo "(unavailable)"
echo "=== docker ==="
docker system df 2>/dev/null | head -3
echo "=== pull speed sample ==="
IMG=debian:bookworm-slim
start=$(date +%s)
if timeout 120 docker pull -q "$IMG" >/dev/null 2>&1; then
  end=$(date +%s)
  size=$(docker image inspect "$IMG" --format '{{.Size}}' 2>/dev/null || echo 0)
  elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
  echo "OK: $((size/1024/1024))MB in ${elapsed}s (~$(( size/1024/1024/elapsed )) MB/s)"
else
  echo "FAILED (Docker Hub unreachable?)"
fi
docker rmi "$IMG" >/dev/null 2>&1 || true
