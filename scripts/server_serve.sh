#!/usr/bin/env bash
# Serve the base model plus the SFT LoRA adapter on the A10.
set -eu
cd /root/paperArts/bench/reporepair-lab
MODEL=/root/paperArts/bench/models/Qwen2.5-Coder-7B-Instruct
ADAPTER=/root/paperArts/bench/reporepair-lab/outputs/sft-qwen-coder-7b
exec .venv-serve/bin/vllm serve "$MODEL" \
    --served-model-name base \
    --enable-lora \
    --lora-modules "sft=$ADAPTER" \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.90 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen2_xml \
    --tool-parser-plugin /root/paperArts/bench/logs/qwen2_xml_parser.py \
    --port 8000 \
    --host 127.0.0.1
