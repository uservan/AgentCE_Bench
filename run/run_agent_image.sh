#!/usr/bin/env bash
set -euo pipefail

AGENT_DIR=run/agent

# Change this to switch models (uncomment the corresponding line):

# === Small models (single GPU / 4 GPUs) ===
# AGENT_SCRIPT=$AGENT_DIR/qwen35_0.8b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_2b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_4b.sh
AGENT_SCRIPT=$AGENT_DIR/qwen35_9b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_27b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_35b_a3b.sh
# AGENT_SCRIPT=$AGENT_DIR/miro_thinker_1_7_mini.sh   # 31B

# === Large models (8 GPUs, sufficient VRAM) ===
# AGENT_SCRIPT=$AGENT_DIR/minimax_m2.sh  
# AGENT_SCRIPT=$AGENT_DIR/minimax_m21.sh                # 229B ~460GB
# AGENT_SCRIPT=$AGENT_DIR/minimax_m25.sh              # 229B ~460GB
# AGENT_SCRIPT=$AGENT_DIR/qwen35_122b_a10b.sh         # 122B ~244GB
# AGENT_SCRIPT=$AGENT_DIR/glm47.sh   
# AGENT_SCRIPT=$AGENT_DIR/miro_thinker_1_7.sh         # 235B ~470GB
# AGENT_SCRIPT=$AGENT_DIR/deepseek_v3_2.sh            # 671B FP8 ~671GB

# === Not recommended (insufficient VRAM or storage) ===
# AGENT_SCRIPT=$AGENT_DIR/qwen35_397b_a17b.sh         # 397B ~800GB, insufficient KV cache space
# AGENT_SCRIPT=$AGENT_DIR/glm5.sh                     # 744B FP8, insufficient KV cache space
# AGENT_SCRIPT=$AGENT_DIR/kimi_k2_5.sh                # 1T, cannot fit in 8xH200

nohup singularity exec --cleanenv --nv \
  --bind $HOME:$HOME \
  --bind /scratch:/scratch \
  --bind /tmp:/tmp \
  /scratch/pioneer/jobs/user/save/images/vllm_0.17.1.sif \
  bash "$AGENT_SCRIPT" \
  > run/vllm_server.log 2>&1 &

disown

