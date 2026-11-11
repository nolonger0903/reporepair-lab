#!/usr/bin/env bash
# Remove leftover SWE-bench images using the same logic as the collector.
set -uo pipefail
echo "=== our containers ==="
ids=$(docker ps -aq --filter "name=minisweagent-")
if [ -n "$ids" ]; then docker rm -f $ids; else echo "(none)"; fi

echo "=== removing leftover seaborn image ==="
for img in $(docker images --format '{{.Repository}}' | grep 'sweb.eval.x86_64.mwaskom'); do
  echo "removing $img"
  docker rmi "$img" 2>&1 | tail -1
done

echo "=== remaining sweb images ==="
docker images --format '{{.Repository}}' | grep sweb.eval || echo "(none)"
echo "=== disk ==="
df -h /mnt/c | tail -1
echo "=== docker df ==="
docker system df | head -3
