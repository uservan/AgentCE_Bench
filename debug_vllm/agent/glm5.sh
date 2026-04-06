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
LOG_FILE=$LOG_DIR/GLM-5-8009.log

CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 vllm serve zai-org/GLM-5-FP8 \
  --host 0.0.0.0 \
  --port 8009 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --gpu-memory-utilization 0.85 \
  --speculative-config.method mtp \
  --speculative-config.num_speculative_tokens 1 \
  --enable-auto-tool-choice \
  --tool-call-parser glm47 \
  --reasoning-parser glm45 \
  > "$LOG_FILE" 2>&1
