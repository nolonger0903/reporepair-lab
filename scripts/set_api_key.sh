#!/usr/bin/env bash
# 保存 DeepSeek API Key 到 mini-swe-agent 全局配置（输入不回显）
set -euo pipefail
mkdir -p ~/.config/mini-swe-agent
printf 'DeepSeek API Key: ' >&2
read -rs key
echo >&2
if [ -z "$key" ]; then
  echo "empty key, aborting" >&2
  exit 1
fi
cat > ~/.config/mini-swe-agent/.env <<EOF
DEEPSEEK_API_KEY=$key
MSWEA_MODEL_NAME=deepseek/deepseek-chat
MSWEA_CONFIGURED=true
LITELLM_LOCAL_MODEL_COST_MAP=True
EOF
chmod 600 ~/.config/mini-swe-agent/.env
echo "saved to ~/.config/mini-swe-agent/.env" >&2
