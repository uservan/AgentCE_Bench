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
LOG_FILE=$LOG_DIR/DeepSeek-V3.2-8007.log

CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 SAFETENSORS_FAST_GPU=1 vllm serve deepseek-ai/DeepSeek-V3.2 \
  --host 0.0.0.0 \
  --port 8007 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --quantization fp8 \
  --tokenizer-mode deepseek_v32 \
  --enable-auto-tool-choice \
  --tool-call-parser deepseek_v32 \
  --reasoning-parser deepseek_v3 \
  > "$LOG_FILE" 2>&1
