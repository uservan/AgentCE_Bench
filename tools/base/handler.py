import json
from typing import Any, Callable

from agent.task import Task

from ..utils import Tool, as_tool
from .error_type import ErrorType
from .messages import Messages


class BaseToolsHandler:
    """各领域 handler 的基类。"""

    domain: str = ""
    STOP_TOKEN: str = "###STOP###"
    current_task: Task = None

    def __init__(self):
        self.tools: dict[str, Callable[..., Any]] = {
            "set_slot": self.set_slot,
            "get_current_grid_state": self.get_current_grid_state,
            "get_slot_id": self.get_slot_id,
            "done": self.done,
        }

    def handle(
        self,
        task: Task,
        tool_name: str,
        tool_args: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        self.current_task = task
        """处理工具调用。task 为 Task 类实例。调用时暂存 task 到 self._current_task，工具函数仅接收 args。"""
        if tool_name not in self.tools:
            return Messages.build_failure_message(
                ErrorType.UNKNOWN_TOOL,
                f"'{tool_name}' for domain '{self.domain}'",
            )
        return self.tools[tool_name](**(tool_args or {}))

    def get_tools(self) -> dict[str, Tool]:
        """Get the tools available in the ToolKit.
            Uses the `as_tool` to convert the functions to Tool objects.

            Returns:
                A dictionary of tools available in the ToolKit.
            """
        # NOTE: as_tool needs to get the function (self.foo), not the `foo(self, ...)`
        # Otherwise, the `self` will exists in the arguments.
        # Therefore, it needs to be called with getattr(self, name)
        my_tools = dict()
        for name, tool in self.tools.items():
            my_tools[name] = as_tool(tool)
        return my_tools

    def _get_current_dataset(self) -> tuple[Any | None, Messages | None]:
        task = self.current_task
        if task is None:
            return None, Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return task.dataset_object, None

    def _parse_string_list_argument(
        self,
        value: Any,
        argument_name: str,
    ) -> tuple[list[str] | None, Messages | None]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return None, Messages.build_failure_message(
                    ErrorType.INVALID_ARGUMENTS,
                    f"{argument_name} string must be a valid JSON list",
                )
        if not isinstance(value, list):
            return None, Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"{argument_name} must be a list",
            )
        if any(not isinstance(item, str) for item in value):
            return None, Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"each element in {argument_name} must be a string",
            )
        return value, None

    def _get_slot(self, row: int, col: int) -> tuple[Any | None, dict[str, Any] | None, Messages | None]:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return None, None, error
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            return None, None, Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "row and col must be integers",
            )

        for slot in dataset.slots:
            if slot.get("row") == row and slot.get("col") == col:
                return dataset, slot, None
        return None, None, Messages.build_failure_message(
            ErrorType.INVALID_ARGUMENTS,
            f"Invalid slot (row={row}, col={col})",
        )

    def _query_slot_candidates(self, row: int, col: int, summary_fields: list[str]) -> Messages:
        dataset, slot, error = self._get_slot(row, col)
        if error is not None:
            return error

        candidates = []
        missing_candidate_ids = []
        for item_id in slot["candidate_ids"]:
            item = dataset.item_pool.get(item_id)
            if item is None:
                missing_candidate_ids.append(item_id)
                continue

            candidate = {"id": item_id}
            for field in summary_fields:
                candidate[field] = item.get(field)
            candidates.append(candidate)

        return Messages.build_success_message({
            "row": slot["row"],
            "col": slot["col"],
            "candidates": candidates,
            "missing_candidate_ids": missing_candidate_ids,
        })

    def _get_item_info(self, id: str) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        if not isinstance(id, str):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "id must be a string")
        item = dataset.item_pool.get(id)
        if item is None:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"Unknown item id: {id}",
            )
        return Messages.build_success_message({
            "id": id,
            "item": item,
        })

    def _get_item_attribute_values(
        self,
        ids: list[str] | str,
        field: str,
        max_items: int = 5,
    ) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error

        parsed_ids, ids_error = self._parse_string_list_argument(ids, "ids")
        if ids_error is not None:
            return ids_error
        if len(parsed_ids) > max_items:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"ids can contain at most {max_items} items",
            )
        if not isinstance(field, str) or not field.strip():
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "field must be a non-empty string",
            )
        normalized_field = field.strip()

        items = {}
        missing_ids = []
        for item_id in parsed_ids:
            item = dataset.item_pool.get(item_id)
            if item is None:
                missing_ids.append(item_id)
                continue
            items[item_id] = item.get(normalized_field)

        return Messages.build_success_message({
            "field": normalized_field,
            "items": items,
            "missing_ids": missing_ids,
        })

    def _check_row_constraints(self, row: int) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        try:
            row = int(row)
        except (TypeError, ValueError):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "row must be an integer")

        try:
            from data_generation.validation import validate_row_constraints
        except ImportError:
            from validation import validate_row_constraints  # type: ignore

        is_valid, reason = validate_row_constraints(
            solution=self.current_task.agent_solution,
            domain=dataset.domain,
            row_index=row,
            row_constraints=dataset.row_constraints,
            item_pool=dataset.item_pool,
            slots=dataset.slots,
        )
        return Messages.build_success_message({
            "row": row,
            "is_valid": is_valid,
            "reason": reason,
        })

    def _check_col_constraints(self, col: int) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        try:
            col = int(col)
        except (TypeError, ValueError):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "col must be an integer")

        try:
            from data_generation.validation import validate_col_constraints
        except ImportError:
            from validation import validate_col_constraints  # type: ignore

        is_valid, reason = validate_col_constraints(
            solution=self.current_task.agent_solution,
            domain=dataset.domain,
            col_index=col,
            col_constraints=dataset.col_constraints,
            item_pool=dataset.item_pool,
            slots=dataset.slots,
        )
        return Messages.build_success_message({
            "col": col,
            "is_valid": is_valid,
            "reason": reason,
        })

    def _check_global_constraints(self) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error

        try:
            from data_generation.validation import validate_global_constraints
        except ImportError:
            from validation import validate_global_constraints  # type: ignore

        is_valid, reason = validate_global_constraints(
            solution=self.current_task.agent_solution,
            domain=dataset.domain,
            global_constraints=dataset.global_constraints,
            item_pool=dataset.item_pool,
            slots=dataset.slots,
        )
        return Messages.build_success_message({
            "is_valid": is_valid,
            "reason": reason,
        })

    def done(self) -> Messages:
        """Call this function when you are done with the task."""
        return Messages(status="success", messages=self.STOP_TOKEN, data={})

    def set_slot(self, row: int, col: int, id: str | None = None) -> Messages:
        """Fill or clear a specific slot.

        row: Row index as an integer.
        col: Column index as an integer.
        id: Item id as a string. Pass null or an empty string to clear the slot.
        """
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "row and col must be integers")
        solution = task.agent_solution
        if row < 0 or row >= len(solution) or col < 0 or col >= len(solution[0]):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, f"Invalid slot (row={row}, col={col})")
        if id is not None and id != "":
            solution[row][col] = str(id)
        else:
            solution[row][col] = None
        return Messages.build_success_message({"row": row, "col": col, "id": solution[row][col]})

    def get_current_grid_state(self) -> Messages:
        """Return the full current grid state."""
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return Messages.build_success_message({"slots": task.agent_solution})

    def get_slot_id(self, row: int, col: int) -> Messages:
        """Get the item id currently stored in a slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "row and col must be integers")
        solution = task.agent_solution
        if row < 0 or row >= len(solution) or col < 0 or col >= len(solution[0]):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, f"Invalid slot (row={row}, col={col})")
        return Messages.build_success_message({"row": row, "col": col, "id": solution[row][col]})
