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
LOG_FILE=$LOG_DIR/MiniMax-M2.5-8005.log

CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 SAFETENSORS_FAST_GPU=1 vllm serve MiniMaxAI/MiniMax-M2.5 \
  --host 0.0.0.0 \
  --port 8005 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --enable-expert-parallel \
  --enable-auto-tool-choice \
  --tool-call-parser minimax_m2 \
  --reasoning-parser minimax_m2_append_think \
  --compilation-config '{"cudagraph_mode":"PIECEWISE"}' \
  > "$LOG_FILE" 2>&1
