#!/usr/bin/env bash
# Read-only survey of the training server. Makes no changes.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$HOST" 'bash -s' <<'REMOTE'
echo "=== host ==="
hostname
uname -a
echo "=== cpu/mem ==="
nproc
free -g | head -2
echo "=== disk ==="
df -h / /root 2>/dev/null | grep -v tmpfs
echo "=== gpu ==="
nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader || echo "nvidia-smi unavailable"
echo "=== toolchain ==="
python3 --version 2>&1 || echo "no python3"
docker --version 2>&1 || echo "no docker"
docker info --format '{{.Driver}} / {{.DockerRootDir}}' 2>&1 | head -1 || true
echo "=== workdir ==="
ls -la /root/paperArts 2>/dev/null || echo "no /root/paperArts"
echo "=== existing disk pressure from docker ==="
docker system df 2>/dev/null || true
REMOTE
