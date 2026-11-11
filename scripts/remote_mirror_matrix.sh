#!/usr/bin/env bash
# Ask each candidate registry whether it can serve the SWE-bench image manifest.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}
REPO=swebench/sweb.eval.x86_64.pallets_1776_flask-4045
ACCEPT='application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.index.v1+json'

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" "bash -s" <<REMOTE
REPO=$REPO
ACCEPT='$ACCEPT'
printf '%-32s %-6s %-8s\n' MIRROR /v2/ manifest
for m in registry-1.docker.io docker.m.daocloud.io docker.1ms.run dockerproxy.com \
         docker.1panel.live hub.rat.dev dockerpull.org docker.rainbond.cc \
         docker.hlmirror.com dockerhub.icu docker.anyhub.us.kg mirror.ccs.tencentyun.com; do
  v2=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "https://\$m/v2/" 2>/dev/null || echo ERR)
  man=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H "Accept: \$ACCEPT" \\
        "https://\$m/v2/\$REPO/manifests/latest" 2>/dev/null || echo ERR)
  printf '%-32s %-6s %-8s\n' "\$m" "\$v2" "\$man"
done
REMOTE
