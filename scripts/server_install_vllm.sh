#!/usr/bin/env bash
set -eu
cd /root/paperArts/bench/reporepair-lab
rm -rf .venv-serve
uv venv .venv-serve --python 3.10
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
uv pip install --python .venv-serve/bin/python "vllm==0.7.3"
