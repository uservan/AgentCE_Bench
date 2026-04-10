import copy
import random
from typing import Any

from .task_prompt import build_initial_messages, is_done_tool_message

try:
    from env.load_datasets.loader import SavedDatasetObject
except ImportError:
    SavedDatasetObject = Any  # type: ignore


DEFAULT_MAX_QUERY_IDS = 5
DEFAULT_MAX_QUERY_FIELDS = 5


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
    New datasets use partial_solution directly from the data file.
    For backward compatibility with old data, falls back to a copy of truth_solution if the field is missing.
    """
    del seed
    partial_solution = getattr(dataset_object, "partial_solution", None)
    if partial_solution:
        return copy.deepcopy(partial_solution)
    return copy.deepcopy(dataset_object.truth_solution)


def _count_slot_query_budget(
    slot: dict[str, Any], hidden_slot_count: int, extra_query_num: int = 0
) -> int:
    active_rule_names = slot.get("slot_constraints", {}).get("active_rule_names", [])
    return len(active_rule_names) + hidden_slot_count + extra_query_num


class Task:
    """Task class encapsulating a single task run."""

    def __init__(
        self,
        dataset_object: SavedDatasetObject,
        max_steps: int = 1000,
        tool_failure_rate: float = 0.0,
        tools_domain_only: bool = True,
        max_query_ids: int = DEFAULT_MAX_QUERY_IDS,
        max_query_fields: int = DEFAULT_MAX_QUERY_FIELDS,
        check_include_reason: bool = False,
        global_check_alpha: float | None = 1,
        extra_query_num: int = 2,
        seed: int | None = None,
        max_length_truncations: int = 3,
    ):
        self.dataset_object: SavedDatasetObject = dataset_object
        self.max_steps = max_steps
        self.tool_failure_rate = tool_failure_rate
        self.tools_domain_only = tools_domain_only
        self.max_query_ids = max_query_ids
        self.max_query_fields = max_query_fields
        self.check_include_reason = check_include_reason
        self.global_check_alpha = global_check_alpha
        self.extra_query_num = extra_query_num
        self.seed = seed
        self.max_length_truncations = max_length_truncations
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
        self.global_check_budget = (
            None
            if global_check_alpha is None or global_check_alpha == -1
            else max(0, int(global_check_alpha * len(self.hidden_slot_path)))
        )
        self.global_check_calls = 0
        self.hidden_slot_query_budget: dict[tuple[int, int], int | None] = {}
        self.hidden_slot_query_calls: dict[tuple[int, int], int] = {}
        total_hidden_slot_count = len(self.hidden_slot_path)
        for slot in getattr(dataset_object, "slots", []):
            row = slot.get("row")
            col = slot.get("col")
            if not isinstance(row, int) or not isinstance(col, int):
                continue
            slot_position = (row, col)
            if extra_query_num == -1:
                budget = None
            else:
                budget = max(0, _count_slot_query_budget(slot, total_hidden_slot_count, extra_query_num))
            self.hidden_slot_query_budget[slot_position] = budget
            self.hidden_slot_query_calls[slot_position] = 0

    def build_initial_messages(self) -> list[dict[str, Any]]:
        """Build the initial message list."""
        return build_initial_messages(self)

    def is_finished(self, messages) -> bool:
        """Determine whether the task is finished based on messages."""
        for msg in messages:
            if is_done_tool_message(msg):
                return True
        return False

    def eval(self) -> Any:
        """Evaluate the task completion status."""
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

    def can_call_hidden_slot_query(self, row: int, col: int) -> bool:
        slot_position = (row, col)
        if slot_position not in self.hidden_slot_query_budget:
            return False
        budget = self.hidden_slot_query_budget[slot_position]
        if budget is None:
            return True
        return self.hidden_slot_query_calls.get(slot_position, 0) < budget

    def record_hidden_slot_query_call(self, row: int, col: int) -> None:
        slot_position = (row, col)
        if slot_position not in self.hidden_slot_query_calls:
            return
        self.hidden_slot_query_calls[slot_position] += 1

    def get_remaining_hidden_slot_queries(self, row: int, col: int) -> int | None:
        slot_position = (row, col)
        if slot_position not in self.hidden_slot_query_budget:
            return None
        budget = self.hidden_slot_query_budget[slot_position]
        if budget is None:
            return None  # unlimited
        return max(0, budget - self.hidden_slot_query_calls.get(slot_position, 0))

    def get_global_check_budget_status(self) -> dict[str, int | None]:
        return {
            "remaining_global_checks": self.get_remaining_global_checks(),
            "global_check_budget": self.global_check_budget,
            "global_check_calls": self.global_check_calls,
        }

    def can_call_global_check(self) -> bool:
        if self.global_check_budget is None:
            return True
        return self.global_check_calls < self.global_check_budget

    def record_global_check_call(self) -> None:
        self.global_check_calls += 1

    def get_remaining_global_checks(self) -> int | None:
        if self.global_check_budget is None:
            return None
        return max(0, self.global_check_budget - self.global_check_calls)

    def call_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Call a tool and forward to call_saved_dataset_tool."""
        from env.tools import call_saved_dataset_tool
        return call_saved_dataset_tool(
            task=self,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_failure_rate=self.tool_failure_rate,
            **kwargs,
        )

    def get_tool_schemas(self) -> list[Any]:
        """Get the tool schemas for this task's domain."""
        try:
            from env.tools import get_saved_dataset_tool_schemas
            domain = self.dataset_object.domain if self.tools_domain_only else None
            tool_schemas = [tool.openai_schema for tool in get_saved_dataset_tool_schemas(domain=domain)]
            rng = random.Random(self.seed) if self.seed is not None else random.Random()
            rng.shuffle(tool_schemas)
            return tool_schemas
        except ImportError:
            return []
