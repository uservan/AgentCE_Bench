import copy
import json
import random
from typing import Any

from .task_prompt import build_initial_messages, is_done_tool_message

try:
    from load_datasets.loader import SavedDatasetObject
except ImportError:
    SavedDatasetObject = Any  # type: ignore


def _build_partial_solution(truth_solution: list, hidden_rate: float, seed: int | None = None) -> list:
    """
    根据 hidden_rate 随机将对应比例的 slot 设为 None，得到类似 truth_solution 的 partial_solution。
    """
    if hidden_rate <= 0:
        return copy.deepcopy(truth_solution)
    solution = copy.deepcopy(truth_solution)
    positions = [
        (row_idx, col_idx)
        for row_idx, row in enumerate(truth_solution)
        for col_idx in range(len(row))
    ]
    if not positions:
        return solution
    n_hide = int(len(positions) * hidden_rate)
    if n_hide <= 0:
        return solution
    rng = random.Random(seed) if seed is not None else random
    to_hide = rng.sample(positions, min(n_hide, len(positions)))
    for row_idx, col_idx in to_hide:
        solution[row_idx][col_idx] = None
    return solution


class Task:
    """Task 类，封装一次任务。"""

    def __init__(
        self,
        dataset_object: SavedDatasetObject,
        hidden_rate: float = 0.0,
        max_steps: int = 1000,
        tool_failure_rate: float = 0.0,
        tools_domain_only: bool = True,
        seed: int | None = None,
    ):
        self.dataset_object: SavedDatasetObject = dataset_object
        self.hidden_rate = hidden_rate
        self.max_steps = max_steps
        self.tool_failure_rate = tool_failure_rate
        self.tools_domain_only = tools_domain_only
        self.seed = seed
        self.partial_solution: list = _build_partial_solution(
            dataset_object.truth_solution,
            hidden_rate=hidden_rate,
            seed=seed,
        )
        self.agent_solution: list = copy.deepcopy(self.partial_solution)

    def build_initial_messages(self) -> list[dict[str, Any]]:
        """构建初始消息列表。"""
        return build_initial_messages(self)

    def is_finished(self, messages) -> bool:
        """根据消息判断任务是否完成。"""
        for msg in messages:
            if is_done_tool_message(msg):
                return True
        return False

    def eval(self) -> Any:
        """评估任务完成情况。"""
        try:
            from data_generation.validation import (
                validate_col_constraints,
                validate_global_constraints,
                validate_row_constraints,
            )
        except ImportError:
            from validation import (
                validate_col_constraints,
                validate_global_constraints,
                validate_row_constraints,
            )

        solution = self.agent_solution
        dataset = self.dataset_object
        rows = dataset.meta["rows"]
        cols = dataset.meta["cols"]

        if len(solution) != rows or any(len(row) != cols for row in solution):
            return {
                "score": False,
                "reason": f"solution shape does not match expected {rows}x{cols} grid",
            }

        if any(item_id is None for row in solution for item_id in row):
            return {
                "score": False,
                "reason": "solution still contains empty slots",
            }

        for row_index in range(rows):
            is_valid, reason = validate_row_constraints(
                solution=solution,
                domain=dataset.domain,
                row_index=row_index,
                row_constraints=dataset.row_constraints,
                item_pool=dataset.item_pool,
                slots=dataset.slots,
            )
            if not is_valid:
                return {"score": False, "reason": reason}

        for col_index in range(cols):
            is_valid, reason = validate_col_constraints(
                solution=solution,
                domain=dataset.domain,
                col_index=col_index,
                col_constraints=dataset.col_constraints,
                item_pool=dataset.item_pool,
                slots=dataset.slots,
            )
            if not is_valid:
                return {"score": False, "reason": reason}

        is_valid, reason = validate_global_constraints(
            solution=solution,
            domain=dataset.domain,
            global_constraints=dataset.global_constraints,
            item_pool=dataset.item_pool,
            slots=dataset.slots,
        )
        if not is_valid:
            return {"score": False, "reason": reason}

        return {"score": True, "reason": None}

    def call_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """调用工具，转发给 call_saved_dataset_tool。"""
        from tools import call_saved_dataset_tool
        return call_saved_dataset_tool(
            task=self,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_failure_rate=self.tool_failure_rate,
            **kwargs,
        )

    def get_tool_schemas(self) -> list[Any]:
        """获取该任务领域的 tool schemas。"""
        try:
            from tools import get_saved_dataset_tool_schemas
            domain = self.dataset_object.domain if self.tools_domain_only else None
            tool_schemas = [tool.openai_schema for tool in get_saved_dataset_tool_schemas(domain=domain)]
            rng = random.Random(self.seed) if self.seed is not None else random.Random()
            rng.shuffle(tool_schemas)
            return tool_schemas
        except ImportError:
            return []
