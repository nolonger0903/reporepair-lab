#!/usr/bin/env bash
# Better local pull-speed sample across differently sized images + registry config.
set -uo pipefail
echo "=== docker registry config ==="
docker info 2>/dev/null | grep -iA3 "registry mirrors" || echo "(no mirrors configured)"
echo "=== pull samples ==="
test_one() {
  img=$1
  [ -n "${2:-}" ] && prev=$2 || prev=""
  start=$(date +%s)
  if timeout 300 docker pull -q "$img" >/dev/null 2>&1; then
    end=$(date +%s)
    size=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
    mb=$((size/1024/1024)); elapsed=$((end-start)); [ "$elapsed" -lt 1 ] && elapsed=1
    echo "$img: ${mb}MB in ${elapsed}s (~$((mb/elapsed)) MB/s uncompressed)"
  else
    echo "$img: FAILED/TIMEOUT"
  fi
  docker rmi "$img" >/dev/null 2>&1 || true
}
test_one ubuntu:22.04
test_one node:20-slim
