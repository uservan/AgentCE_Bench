# debug.py - 测试 cached_agent_benchmark 的 main

import os
import sys

os.environ.setdefault("OPENAI_API_KEY", "EMPTY")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import main
from config import MODELS

if __name__ == "__main__":
    # sh command: 
    #   nohup python debug_vllm2/debug.py > debug_vllm2/debug_log/qwen35_122b_a10b.log 2>&1 &
    #   disown 
    cfg = MODELS["qwen35_122b_a10b"]
    main(
        model=cfg["model"],
        agent_params=cfg["agent_params"],
        domain=["course"], # "all",
        data_dir="data/5x7",
        max_steps=2000,
        max_query_ids=5,
        max_query_fields=5,
        tool_failure_rates=[0.0,0.1,0.3], # [0.0], #
        num_trials=1,
        tools_domain_only=True,
        save_path="/scratch/pioneer/jobs/user/save/cached_results2/",
        overwrite_results=False,
        check_include_reason=False,
        global_check_alpha=-1,
        extra_query_num=-1,
        seed=42,
        hidden_slots=None,
        branch_budget=None,
        max_workers=64,
        max_length_truncations=3,
    )
