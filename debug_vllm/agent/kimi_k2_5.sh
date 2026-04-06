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
LOG_FILE=$LOG_DIR/Kimi-K2.5-8008.log

CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 vllm serve moonshotai/Kimi-K2.5 \
  --host 0.0.0.0 \
  --port 8008 \
  --trust-remote-code \
  -tp 8 \
  --mm-encoder-tp-mode data \
  --enable-auto-tool-choice \
  --tool-call-parser kimi_k2 \
  --reasoning-parser kimi_k2 \
  > "$LOG_FILE" 2>&1
