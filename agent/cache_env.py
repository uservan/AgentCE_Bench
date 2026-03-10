import json
import random
from typing import Any

from agent.agent import Agent, AssistantMessage
from cached_datasets import BaseDataset, MergedTask

class CacheEnv:
    """CacheEnv 负责遍历 dataset、调用 agent，并基于 task 做评估。"""

    def __init__(
        self,
        max_steps=None,
        num_trials=1,
        together_tasks=None,
        tool_failure_rates=None,
        seed=42,
    ):
        self.max_steps = max_steps
        self.num_trials = num_trials
        self.together_tasks = together_tasks or [1]
        self.tool_failure_rates = tool_failure_rates or [0.0]
        random.seed(seed)
        self.seeds = [random.randint(0, 1000000) for _ in range(num_trials)]

    def run_task(self, merge_task:MergedTask, agent:Agent, trial_id=0, together_task_size=1, tool_failure_rate=0.0):
        """
        执行单个 task，拿到 messages，用 task.eval 打分，并把分数追加到 messages。
        """
        assistant_message: AssistantMessage = agent.generate(
            merge_task,
            max_steps=self.max_steps,
            tool_failure_rate=tool_failure_rate,
            seed=self.seeds[trial_id],
        )
        messages = list(getattr(assistant_message, "raw_messages", []) or [])
        score = merge_task.eval(messages)
        assistant_message.set_score(score)

        return assistant_message
    
    def run(self, dataset: BaseDataset, agent: Agent, save_path):
        """
        遍历整个 dataset，执行全部 task，汇总结果并保存到 JSON 文件。
        """
        results = {}
        total_score = 0.0
        scored_count = 0
        for together_task_size in self.together_tasks:
            merged_tasks = dataset._build_combined_tasks(dataset, together_task_size)
            for tool_failure_rate in self.tool_failure_rates:
                result_key = f"task_size={together_task_size},tool_failure_rate={tool_failure_rate}"
                results[result_key] = []
                for merge_task in merged_tasks:
                    for trial_id in range(self.num_trials):
                        result: AssistantMessage = self.run_task(
                            merge_task,
                            agent,
                            trial_id=trial_id,
                            together_task_size=together_task_size,
                            tool_failure_rate=tool_failure_rate,
                        )
                        results[result_key].append(result)

                        numeric_score = self._extract_numeric_score(result.score)
                        if numeric_score is not None:
                            total_score += numeric_score
                            scored_count += 1

        output = {
            "dataset": dataset.name,
            "base_task_count": len(dataset),
            "together_tasks": self.together_tasks,
            "tool_failure_rates": self.tool_failure_rates,
            "num_trials": self.num_trials,
            "max_steps": self.max_steps,
            "result_count": sum(len(group_results) for group_results in results.values()),
            "scored_count": scored_count,
            "total_score": total_score,
            "average_score": total_score / scored_count if scored_count else None,
            "results": results,
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return output

