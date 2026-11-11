#!/usr/bin/env bash
# Measure local Docker Hub pull throughput (WSL + Docker Desktop).
set -euo pipefail
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897

IMG=alpine:3.20
start=$(date +%s)
if docker pull -q "$IMG" >/dev/null 2>&1; then
  end=$(date +%s)
  size=$(docker image inspect "$IMG" --format '{{.Size}}' 2>/dev/null || echo 0)
  echo "OK: $((size/1024/1024))MB in $((end-start))s"
else
  echo "FAILED"
fi
docker rmi "$IMG" >/dev/null 2>&1 || true
