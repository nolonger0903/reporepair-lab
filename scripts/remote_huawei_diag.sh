#!/usr/bin/env bash
# Diagnose why Huawei SWR fails for the swebench namespace.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
M=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io
echo "=== manifest probe (HTTP) ==="
for repo in swebench/sweb.eval.x86_64.pallets_1776_flask-4045 bitnami/nginx grafana/grafana; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 \
    -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
    "https://$M/v2/$repo/manifests/latest")
  printf '%-55s %s\n' "$repo" "$code"
done
echo "=== verbose pull error ==="
timeout 90 docker pull "$M/swebench/sweb.eval.x86_64.pallets_1776_flask-4045:latest" 2>&1 | tail -4
echo "=== control: namespaced image ==="
if timeout 120 docker pull -q "$M/bitnami/nginx:latest" >/dev/null 2>&1; then
  echo "namespaced pull OK"
  docker rmi "$M/bitnami/nginx:latest" >/dev/null 2>&1 || true
else
  echo "namespaced pull FAILED"
fi
REMOTE
