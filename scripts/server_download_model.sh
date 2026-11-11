#!/usr/bin/env bash
# Download Qwen2.5-Coder-7B-Instruct from ModelScope (fast inside CN) with resume.
set -u
DEST=/root/paperArts/bench/models/Qwen2.5-Coder-7B-Instruct
BASE=https://modelscope.cn/models/Qwen/Qwen2.5-Coder-7B-Instruct/resolve/master
mkdir -p "$DEST"
cd "$DEST"

FILES="config.json generation_config.json merges.txt model.safetensors.index.json tokenizer.json tokenizer_config.json vocab.json model-00001-of-00004.safetensors model-00002-of-00004.safetensors model-00003-of-00004.safetensors model-00004-of-00004.safetensors"

for f in $FILES; do
    echo "=== $f $(date +%H:%M:%S)"
    if wget -c --tries=20 --timeout=60 --waitretry=5 -q "$BASE/$f" -O "$f"; then
        echo "OK $f $(du -h "$f" | cut -f1)"
    else
        echo "FAIL $f"
    fi
done
echo "ALL DONE $(date +%H:%M:%S)"
