#!/usr/bin/env bash
set -euo pipefail

unset CC
unset CXX
unset CUDAHOSTCXX
unset LDSHARED
unset AR
unset NM
unset RANLIB

which python || true
which gcc || true
which g++ || true
env | grep -E '^(CC|CXX|CUDA|CONDA|LD_LIBRARY_PATH|PATH)=' || true

export HF_TOKEN=
export HF_HOME=/scratch/pioneer/jobs/user/huggingface

LOG_DIR=/home/user/ondemand/program/cached_agent_benchmark/debug_vllm2/log
LOG_FILE=$LOG_DIR/Qwen3.5-0.8B-8003.log

CUDA_VISIBLE_DEVICES=3 vllm serve Qwen/Qwen3.5-0.8B \
  --host 0.0.0.0 \
  --port 8003 \
  --gpu-memory-utilization 0.90 \
  --reasoning-parser qwen3 \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  > "$LOG_FILE" 2>&1
