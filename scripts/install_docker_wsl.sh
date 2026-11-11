#!/usr/bin/env bash
# 在 WSL Ubuntu 中安装原生 Docker 引擎（替代 Docker Desktop 的 CLI 转发）
set -euo pipefail

echo "==> 移除指向 Docker Desktop 的 CLI 符号链接"
sudo rm -f /usr/bin/docker /usr/bin/docker-compose || true

echo "==> 安装 docker.io（Ubuntu 官方源）"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive sudo apt-get install -y docker.io

echo "==> 启用并启动 dockerd"
sudo systemctl enable --now docker

echo "==> 确保当前用户在 docker 组"
sudo usermod -aG docker "$USER"

echo "==> 版本"
sudo docker version --format 'server {{.Server.Version}}'
echo
echo "注意：docker 组权限需要新开一个 shell 才生效。"
echo "当前会话可用: sg docker -c 'docker ps'"
