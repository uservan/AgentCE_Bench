import copy
import random
from typing import Any

from .task_prompt import build_initial_messages, is_done_tool_message

try:
    from load_datasets.loader import SavedDatasetObject
except ImportError:
    SavedDatasetObject = Any  # type: ignore


DEFAULT_MAX_QUERY_IDS = 5
DEFAULT_MAX_QUERY_FIELDS = 6


def _build_hidden_slot_path(dataset_object: SavedDatasetObject) -> list[tuple[int, int]]:
    path: list[tuple[int, int]] = []
    for slot in getattr(dataset_object, "slots", []):
        row = slot.get("row")
        col = slot.get("col")
        if isinstance(row, int) and isinstance(col, int):
            path.append((row, col))
    return path


def _resolve_partial_solution(
    dataset_object: SavedDatasetObject,
    seed: int | None = None,
) -> list:
    """
    新数据集直接使用数据文件中的 partial_solution。
    对旧数据做兼容时，若缺失该字段，则退化为 truth_solution 的拷贝。
    """
    del seed
    partial_solution = getattr(dataset_object, "partial_solution", None)
    if partial_solution:
        return copy.deepcopy(partial_solution)
    return copy.deepcopy(dataset_object.truth_solution)


class Task:
    """Task 类，封装一次任务。"""

    def __init__(
        self,
        dataset_object: SavedDatasetObject,
        max_steps: int = 1000,
        tool_failure_rate: float = 0.0,
        tools_domain_only: bool = True,
        max_query_ids: int = DEFAULT_MAX_QUERY_IDS,
        max_query_fields: int = DEFAULT_MAX_QUERY_FIELDS,
        seed: int | None = None,
    ):
        self.dataset_object: SavedDatasetObject = dataset_object
        self.max_steps = max_steps
        self.tool_failure_rate = tool_failure_rate
        self.tools_domain_only = tools_domain_only
        self.max_query_ids = max_query_ids
        self.max_query_fields = max_query_fields
        self.seed = seed
        self.hidden_slots = copy.deepcopy(getattr(dataset_object, "hidden_slots", []))
        self.branch_budget = getattr(dataset_object, "branch_budget", None)
        self.branch_slot_count = getattr(dataset_object, "branch_slot_count", None)
        self.branch_budget_allocations = copy.deepcopy(
            getattr(
                dataset_object,
                "branch_budget_allocations",
                dataset_object.meta.get("branch_budget_allocations", []),
            )
        )
        self.partial_solution: list = _resolve_partial_solution(
            dataset_object,
            seed=seed,
        )
        self.agent_solution: list = copy.deepcopy(self.partial_solution)
        self.hidden_slot_path: list[tuple[int, int]] = _build_hidden_slot_path(dataset_object)
        self.hidden_slot_index_map: dict[tuple[int, int], int] = {
            slot_position: index
            for index, slot_position in enumerate(self.hidden_slot_path)
        }
        self.current_slot_index = 0

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
                validate_global_constraints,
                validate_slot_constraints,
            )
        except ImportError:
            from validation import (
                validate_global_constraints,
                validate_slot_constraints,
            )

        solution = self.agent_solution
        dataset = self.dataset_object
        rows = getattr(dataset, "rows", None) or dataset.meta["rows"]
        cols = getattr(dataset, "cols", None) or dataset.meta["cols"]

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

        for slot in dataset.slots:
            is_valid, reason = validate_slot_constraints(
                solution=solution,
                domain=dataset.domain,
                row_index=slot["row"],
                col_index=slot["col"],
                slot_constraint=slot["slot_constraints"],
                item_pool=dataset.item_pool,
                slots=dataset.slots,
                truth_solution=dataset.truth_solution,
            )
            if not is_valid:
                return {"score": False, "reason": reason}

        is_valid, reason = validate_global_constraints(
            solution=solution,
            domain=dataset.domain,
            global_constraints=dataset.global_constraints,
            item_pool=dataset.item_pool,
            slots=dataset.slots,
            truth_solution=dataset.truth_solution,
        )
        if not is_valid:
            return {"score": False, "reason": reason}

        return {"score": True, "reason": None}

    def get_hidden_slot_index(self, row: int, col: int) -> int | None:
        return self.hidden_slot_index_map.get((row, col))

    def get_current_target_slot(self) -> dict[str, int] | None:
        if self.current_slot_index >= len(self.hidden_slot_path):
            return None
        row, col = self.hidden_slot_path[self.current_slot_index]
        return {
            "index": self.current_slot_index,
            "row": row,
            "col": col,
        }

    def get_previous_target_slot(self) -> dict[str, int] | None:
        if not self.hidden_slot_path:
            return None
        previous_index = min(self.current_slot_index - 1, len(self.hidden_slot_path) - 1)
        if previous_index < 0:
            return None
        row, col = self.hidden_slot_path[previous_index]
        return {
            "index": previous_index,
            "row": row,
            "col": col,
        }

    def get_remaining_hidden_slots(self) -> list[dict[str, int]]:
        remaining: list[dict[str, int]] = []
        for index, (row, col) in enumerate(self.hidden_slot_path[self.current_slot_index:], start=self.current_slot_index):
            remaining.append(
                {
                    "index": index,
                    "row": row,
                    "col": col,
                }
            )
        return remaining

    def get_path_state(self) -> dict[str, Any]:
        return {
            "current_slot_index": self.current_slot_index,
            "current_slot": self.get_current_target_slot(),
            "previous_slot": self.get_previous_target_slot(),
            "remaining_slots": self.get_remaining_hidden_slots(),
            "slot_path": [
                {
                    "index": index,
                    "row": row,
                    "col": col,
                }
                for index, (row, col) in enumerate(self.hidden_slot_path)
            ],
        }

    def can_access_hidden_slot(self, row: int, col: int) -> bool:
        slot_index = self.get_hidden_slot_index(row, col)
        if slot_index is None:
            return False
        return slot_index == self.current_slot_index

    def advance_after_current_slot_fill(self, row: int, col: int) -> None:
        slot_index = self.get_hidden_slot_index(row, col)
        if slot_index is None:
            return
        if slot_index == self.current_slot_index:
            self.current_slot_index = min(self.current_slot_index + 1, len(self.hidden_slot_path))

    def can_clear_previous_hidden_slot(self, row: int, col: int) -> bool:
        slot_index = self.get_hidden_slot_index(row, col)
        if slot_index is None:
            return False
        previous_slot = self.get_previous_target_slot()
        if previous_slot is None:
            return False
        return slot_index == previous_slot["index"]

    def rollback_to_slot(self, row: int, col: int) -> None:
        slot_index = self.get_hidden_slot_index(row, col)
        if slot_index is None:
            return
        self.current_slot_index = slot_index

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
