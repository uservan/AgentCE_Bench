# debug.py - 测试 cached_agent_benchmark 的 main

import os

os.environ.setdefault("OPENAI_API_KEY", "EMPTY")

from main import main

if __name__ == "__main__":
    # 最小配置：单 domain、单 trial、少量步数，使用本地 vLLM
    main(
        model="openai/Qwen/Qwen3.5-9B", # Qwen3.5-9B   Qwen3-8B
        domain=["course"],
        agent_params={
            "api_base": "http://localhost:8000/v1",
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
            "max_tokens": 4096,   # 限制单步输出，避免单次生成过长
            "timeout": 120,       # 单次请求超时（秒），防止卡死
        },
        max_steps=500,  # 复杂任务可降到 50
        max_query_ids=5,
        max_query_fields=5,
        tool_failure_rates=[0.0],
        num_trials=1,
        tools_domain_only=True,
        save_path="results/",
        overwrite_results=False,
        seed=42,
        hidden_slots=[1,5,9,13],   # 先跑简单任务；h5_b8 等复杂任务会很慢
        branch_budget=[0,4,8,10],
    )
