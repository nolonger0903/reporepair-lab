#!/usr/bin/env bash
# Sample download throughput from several non-Docker sources.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
probe() {
  name=$1; url=$2
  out=$(curl -s -o /dev/null --max-time 20 -w '%{speed_download} %{size_download}' "$url" 2>/dev/null || echo "0 0")
  set -- $out
  speed=$1; size=$2
  awk -v n="$name" -v s="$speed" -v z="$size" 'BEGIN{printf "%-22s %8.2f MB/s  (%d bytes sampled)\n", n, s/1048576, z}'
}
echo "=== general egress ==="
probe "tsinghua ubuntu" "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ls-lR.gz"
probe "tsinghua pypi"   "https://pypi.tuna.tsinghua.edu.cn/packages/source/n/numpy/numpy-1.26.4.tar.gz"
probe "hf-mirror"       "https://hf-mirror.com/Qwen/Qwen2.5-0.5B-Instruct/resolve/main/model.safetensors"
REMOTE
