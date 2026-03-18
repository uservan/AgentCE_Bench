import json
import os
import random
from typing import Any, Callable

from .agent import Agent
from .run_result import RunResult
from .task import Task


class CacheEnv:
    """CacheEnv 负责遍历 dataset、调用 agent，并基于 task 做评估。"""

    def __init__(
        self,
        dataset_objects: list,
        max_steps: int = 1000,
        tool_failure_rates: list[float] | None = None,
        num_trials: int = 1,
        tools_domain_only: bool = True,
        max_query_ids: int = 5,
        max_query_fields: int = 6,
        overwrite_results: bool = False,
        seed: int = 42,
    ):
        self.dataset_objects = dataset_objects
        self.max_steps = max_steps
        self.tool_failure_rates = tool_failure_rates or [0.0]
        self.num_trials = num_trials
        self.tools_domain_only = tools_domain_only
        self.max_query_ids = max_query_ids
        self.max_query_fields = max_query_fields
        self.overwrite_results = overwrite_results
        random.seed(seed)
        self.seeds = [random.randint(0, 1000000) for _ in range(num_trials)]

    def get_total_runs(self) -> int:
        return (
            len(self.dataset_objects)
            * len(self.tool_failure_rates)
            * len(self.seeds)
        )

    def run_task(self, task: Task, agent: Agent) -> RunResult:
        """
        执行单个 task，拿到 messages，用 task.eval 打分，并把分数追加到 messages。
        """
        run_result: RunResult = agent.generate(task)
        result = task.eval()
        run_result.set_result(result)

        return run_result

    def run(
        self,
        agent: Agent,
        save_path: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """
        遍历 dataset_objects，执行全部 task，汇总结果并保存到 JSON 文件。
        """
        total_runs = self.get_total_runs()
        output_root = self._resolve_output_root(save_path)
        saved_paths: list[str] = []
        numeric_scores: list[float] = []
        usage_totals: dict[str, float] = {}
        usage_counts: dict[str, int] = {}
        reused_cached_runs = 0
        run_index = 0
        for dataset_obj in self.dataset_objects:
            for tool_failure_rate in self.tool_failure_rates:
                for trial_index, seed in enumerate(self.seeds, start=1):
                    run_index += 1
                    output_path = self._build_output_path(
                        save_root=output_root,
                        model_name=agent.model,
                        instance_id=getattr(dataset_obj, "instance_id", ""),
                        max_query_ids=self.max_query_ids,
                        max_query_fields=self.max_query_fields,
                        tool_failure_rate=tool_failure_rate,
                        trial_index=trial_index,
                    )
                    task = Task(
                        dataset_object=dataset_obj,
                        max_steps=self.max_steps,
                        tool_failure_rate=tool_failure_rate,
                        tools_domain_only=self.tools_domain_only,
                        max_query_ids=self.max_query_ids,
                        max_query_fields=self.max_query_fields,
                        seed=seed,
                    )
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "stage": "start",
                                "run_index": run_index,
                                "total_runs": total_runs,
                                "domain": dataset_obj.domain,
                                "instance_id": getattr(dataset_obj, "instance_id", ""),
                                "tool_failure_rate": tool_failure_rate,
                                "trial_index": trial_index,
                                "num_trials": self.num_trials,
                                "seed": seed,
                                "save_path": output_root,
                            }
                        )
                    if not self.overwrite_results and os.path.exists(output_path):
                        cached_payload = self._load_cached_run_payload(output_path)
                        if self._is_matching_cached_payload(
                            cached_payload=cached_payload,
                            model_name=agent.model,
                            instance_id=getattr(dataset_obj, "instance_id", ""),
                            max_query_ids=self.max_query_ids,
                            max_query_fields=self.max_query_fields,
                            tool_failure_rate=tool_failure_rate,
                            trial_index=trial_index,
                            seed=seed,
                        ):
                            saved_paths.append(output_path)
                            reused_cached_runs += 1
                            cached_run_result = cached_payload.get("run_result", {})
                            numeric_score = self._extract_numeric_score(cached_run_result.get("score"))
                            if numeric_score is not None:
                                numeric_scores.append(numeric_score)
                            self._accumulate_usage(
                                usage=cached_run_result.get("usage", {}),
                                usage_totals=usage_totals,
                                usage_counts=usage_counts,
                            )
                            if progress_callback is not None:
                                progress_callback(
                                    {
                                        "stage": "cached",
                                        "run_index": run_index,
                                        "total_runs": total_runs,
                                        "domain": dataset_obj.domain,
                                        "instance_id": getattr(dataset_obj, "instance_id", ""),
                                        "tool_failure_rate": tool_failure_rate,
                                        "trial_index": trial_index,
                                        "num_trials": self.num_trials,
                                        "seed": seed,
                                        "status": cached_run_result.get("status"),
                                        "result": cached_run_result.get("result"),
                                        "save_path": output_path,
                                    }
                                )
                            continue
                    run_result = self.run_task(task, agent)
                    saved_file_path = self._save_run_result(
                        run_result=run_result,
                        output_path=output_path,
                        instance_id=getattr(dataset_obj, "instance_id", ""),
                        max_query_ids=task.max_query_ids,
                        max_query_fields=task.max_query_fields,
                        model_name=agent.model,
                        tool_failure_rate=tool_failure_rate,
                        trial_index=trial_index,
                        seed=seed,
                    )
                    saved_paths.append(saved_file_path)
                    numeric_score = self._extract_numeric_score(run_result.score)
                    if numeric_score is not None:
                        numeric_scores.append(numeric_score)
                    self._accumulate_usage(
                        usage=run_result.usage,
                        usage_totals=usage_totals,
                        usage_counts=usage_counts,
                    )
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "stage": "finish",
                                "run_index": run_index,
                                "total_runs": total_runs,
                                "domain": dataset_obj.domain,
                                "instance_id": getattr(dataset_obj, "instance_id", ""),
                                "tool_failure_rate": tool_failure_rate,
                                "trial_index": trial_index,
                                "num_trials": self.num_trials,
                                "seed": seed,
                                "status": run_result.status,
                                "result": run_result.result,
                                "save_path": saved_file_path,
                            }
                        )
        average_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else None
        average_usage = {
            key: usage_totals[key] / usage_counts[key]
            for key in usage_totals
            if usage_counts.get(key)
        }
        return {
            "saved_paths": saved_paths,
            "average_score": average_score,
            "average_usage": average_usage,
            "scored_runs": len(numeric_scores),
            "total_runs": total_runs,
            "cached_runs": reused_cached_runs,
        }

    def _resolve_output_root(self, save_path: str) -> str:
        normalized_path = os.path.normpath(save_path)
        if normalized_path.endswith(".json"):
            return os.path.dirname(normalized_path) or "."
        return normalized_path

    def _build_output_path(
        self,
        save_root: str,
        model_name: str,
        instance_id: str,
        max_query_ids: int,
        max_query_fields: int,
        tool_failure_rate: float,
        trial_index: int,
    ) -> str:
        file_name = (
            f"fail-{tool_failure_rate}_"
            f"trial-{trial_index}.json"
        )
        model_dir_name = self._get_model_dir_name(model_name)
        result_instance_id = self._build_result_instance_id(
            instance_id=instance_id,
            max_query_ids=max_query_ids,
            max_query_fields=max_query_fields,
        )
        return os.path.join(save_root, model_dir_name, result_instance_id, file_name)

    def _save_run_result(
        self,
        run_result: RunResult,
        output_path: str,
        instance_id: str,
        max_query_ids: int,
        max_query_fields: int,
        model_name: str,
        tool_failure_rate: float,
        trial_index: int,
        seed: int,
    ) -> str:
        result_instance_id = self._build_result_instance_id(
            instance_id=instance_id,
            max_query_ids=max_query_ids,
            max_query_fields=max_query_fields,
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        payload = {
            "model_name": model_name,
            "instance_id": instance_id,
            "result_instance_id": result_instance_id,
            "max_query_ids": max_query_ids,
            "max_query_fields": max_query_fields,
            "tool_failure_rate": tool_failure_rate,
            "trial_index": trial_index,
            "seed": seed,
            "run_result": run_result.to_dict(),
        }
        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
        return output_path

    def _load_cached_run_payload(self, output_path: str) -> dict[str, Any]:
        with open(output_path, "r", encoding="utf-8") as input_file:
            payload = json.load(input_file)
        return payload if isinstance(payload, dict) else {}

    def _is_matching_cached_payload(
        self,
        cached_payload: dict[str, Any],
        model_name: str,
        instance_id: str,
        max_query_ids: int,
        max_query_fields: int,
        tool_failure_rate: float,
        trial_index: int,
        seed: int,
    ) -> bool:
        return (
            cached_payload.get("model_name") == model_name
            and cached_payload.get("instance_id") == instance_id
            and cached_payload.get("max_query_ids") == max_query_ids
            and cached_payload.get("max_query_fields") == max_query_fields
            and cached_payload.get("tool_failure_rate") == tool_failure_rate
            and cached_payload.get("trial_index") == trial_index
            and cached_payload.get("seed") == seed
            and isinstance(cached_payload.get("run_result"), dict)
        )

    def _get_model_dir_name(self, model_name: str) -> str:
        normalized = model_name.rstrip("/").split("/")
        return normalized[-1] if normalized else model_name

    def _build_result_instance_id(
        self,
        instance_id: str,
        max_query_ids: int,
        max_query_fields: int,
    ) -> str:
        return f"{instance_id}_ids{max_query_ids}_fields{max_query_fields}"

    def _extract_numeric_score(self, score: Any) -> float | None:
        if isinstance(score, (int, float)):
            return float(score)
        if isinstance(score, dict):
            for key in ("score", "final_score", "value"):
                value = score.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
        return None

    def _accumulate_usage(
        self,
        usage: dict[str, Any],
        usage_totals: dict[str, float],
        usage_counts: dict[str, int],
    ) -> None:
        for key, value in usage.items():
            if isinstance(value, (int, float)):
                usage_totals[key] = usage_totals.get(key, 0.0) + float(value)
                usage_counts[key] = usage_counts.get(key, 0) + 1
