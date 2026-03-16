# debug.py - 测试 cached_agent_benchmark 的 main

import os

os.environ.setdefault("OPENAI_API_KEY", "EMPTY")

from main import main

if __name__ == "__main__":
    # 最小配置：单 domain、单 trial、少量步数，使用本地 vLLM
    main(
        model="openai/Qwen/Qwen3-8B",
        domain=["course"],
        agent_params={
            "api_base": "http://localhost:8001/v1",
            "temperature": 0.6,
        },
        hidden_rates=[0.1],
        max_steps=200,
        tool_failure_rates=[0.0],
        num_trials=1,
        tools_domain_only=True,
        save_path="results/debug_output.json",
        seed=42,
    )
