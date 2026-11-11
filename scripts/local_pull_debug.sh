#!/usr/bin/env bash
# Show why the local pull fails.
set -uo pipefail
echo "=== docker daemon ==="
docker version --format 'server={{.Server.Version}}' 2>&1 | tail -2
echo "=== images count ==="
docker images -q 2>/dev/null | wc -l
echo "=== pull attempt ==="
timeout 60 docker pull alpine:3.20 2>&1 | tail -6
