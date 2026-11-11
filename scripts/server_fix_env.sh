#!/usr/bin/env bash
set -eu
cd /root/paperArts/bench/reporepair-lab
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
uv pip install --python .venv-train/bin/python "transformers<5" "peft<0.15" "trl<1"
