import json
import random
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
            "get_current_target_slot": self.get_current_target_slot,
            "get_previous_target_slot": self.get_previous_target_slot,
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

    def _build_slot_path_error(self, row: int, col: int) -> Messages:
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        path_state = task.get_path_state()
        current_slot = path_state.get("current_slot")
        previous_slot = path_state.get("previous_slot")
        return Messages.build_failure_message(
            ErrorType.INVALID_ARGUMENTS,
            (
                f"Hidden slot (row={row}, col={col}) is not accessible yet. "
                "Follow the hidden-slot path and only work on the current target slot. "
                "The only rollback allowed is clearing the previous hidden slot via `set_slot`. "
                f"Current target: {current_slot}. Previous slot: {previous_slot}."
            ),
        )

    def _ensure_hidden_slot_access(self, row: int, col: int) -> Messages | None:
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        slot_index = task.get_hidden_slot_index(row, col)
        if slot_index is None:
            return None
        if task.can_access_hidden_slot(row, col):
            return None
        return self._build_slot_path_error(row, col)

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

    def _allowed_item_fields(self, dataset: Any) -> list[str]:
        if not getattr(dataset, "item_pool", None):
            return []
        sample_item = next(iter(dataset.item_pool.values()), None)
        if not isinstance(sample_item, dict):
            return []
        return sorted(key for key in sample_item.keys() if key != "id")

    def _get_allowed_lookup_item_ids(self) -> tuple[set[str], Messages | None]:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return set(), error
        task = self.current_task
        if task is None:
            return set(), Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")

        allowed_ids: set[str] = set()

        # Non-hidden slots stay visible and can always be inspected.
        for row in task.partial_solution:
            for item_id in row:
                if item_id is not None:
                    allowed_ids.add(str(item_id))

        # The current hidden slot's candidate options are also inspectable.
        current_target = task.get_current_target_slot()
        if current_target is not None:
            _, slot, slot_error = self._get_slot(current_target["row"], current_target["col"])
            if slot_error is not None:
                return set(), slot_error
            if slot is not None and slot.get("is_hidden"):
                for item_id in slot.get("candidate_ids", []):
                    if item_id is not None:
                        allowed_ids.add(str(item_id))

        return allowed_ids, None

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
        if 0 <= row < len(dataset.truth_solution) and 0 <= col < len(dataset.truth_solution[0]):
            return dataset, {
                "row": row,
                "col": col,
                "truth_id": dataset.truth_solution[row][col],
                "is_hidden": False,
            }, None
        return None, None, Messages.build_failure_message(
            ErrorType.INVALID_ARGUMENTS,
            f"Invalid slot (row={row}, col={col})",
        )

    def _query_slot_candidates(self, row: int, col: int, summary_fields: list[str]) -> Messages:
        dataset, slot, error = self._get_slot(row, col)
        if error is not None:
            return error

        if not slot.get("is_hidden"):
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "Slot candidate queries are only allowed for the current hidden slot.",
            )
        access_error = self._ensure_hidden_slot_access(slot["row"], slot["col"])
        if access_error is not None:
            return access_error

        candidates = []
        missing_candidate_ids = []
        candidate_ids = list(slot.get("candidate_ids", []))
        random.shuffle(candidate_ids)
        for item_id in candidate_ids:
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
            "is_hidden": True,
            "candidates": candidates,
            "missing_candidate_ids": missing_candidate_ids,
        })

    def _get_item_info(self, id: str) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        if not isinstance(id, str):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "id must be a string")
        allowed_ids, allowed_ids_error = self._get_allowed_lookup_item_ids()
        if allowed_ids_error is not None:
            return allowed_ids_error
        if id not in allowed_ids:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    f"Item id {id} is not accessible. "
                    "You may only inspect ids from non-hidden slots or from the current hidden slot's candidates."
                ),
            )
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
        field: str | list[str],
        max_items: int | None = None,
        max_fields: int | None = None,
    ) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        effective_max_items = (
            max_items
            if max_items is not None
            else getattr(self.current_task, "max_query_ids", 5)
        )
        effective_max_fields = (
            max_fields
            if max_fields is not None
            else getattr(self.current_task, "max_query_fields", 6)
        )

        parsed_ids, ids_error = self._parse_string_list_argument(ids, "ids")
        if ids_error is not None:
            return ids_error
        if len(parsed_ids) > effective_max_items:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"ids can contain at most {effective_max_items} items",
            )

        if isinstance(field, str):
            stripped_field = field.strip()
            parsed_field = None
            if stripped_field.startswith("["):
                try:
                    parsed_field = json.loads(stripped_field)
                except json.JSONDecodeError:
                    parsed_field = None
            if isinstance(parsed_field, list):
                fields = parsed_field
            else:
                fields = [stripped_field] if stripped_field else []
        elif isinstance(field, list):
            fields = field
        else:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "field must be a string or a list of attribute names",
            )
        if any(not isinstance(item, str) for item in fields):
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "each field must be a string",
            )
        fields = [item.strip() for item in fields if item.strip()]
        if not fields:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "field must specify at least one attribute name",
            )
        if len(fields) > effective_max_fields:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"field can specify at most {effective_max_fields} attributes",
            )
        allowed_lookup_ids, allowed_lookup_error = self._get_allowed_lookup_item_ids()
        if allowed_lookup_error is not None:
            return allowed_lookup_error
        inaccessible_ids = [item_id for item_id in parsed_ids if item_id not in allowed_lookup_ids]
        if inaccessible_ids:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    "ids contain inaccessible item(s): "
                    + ", ".join(inaccessible_ids)
                    + ". You may only inspect ids from non-hidden slots or from the current hidden slot's candidates."
                ),
            )
        allowed_fields = self._allowed_item_fields(dataset)
        invalid_fields = [item for item in fields if item not in allowed_fields]
        if invalid_fields:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "unknown field(s): "
                + ", ".join(invalid_fields)
                + ". allowed fields: "
                + ", ".join(allowed_fields),
            )

        items = {}
        missing_ids = []
        for item_id in parsed_ids:
            item = dataset.item_pool.get(item_id)
            if item is None:
                missing_ids.append(item_id)
                continue
            if len(fields) == 1:
                items[item_id] = item.get(fields[0])
            else:
                items[item_id] = {f: item.get(f) for f in fields}

        return Messages.build_success_message({
            "fields": fields,
            "items": items,
            "missing_ids": missing_ids,
        })

    def _check_slot_constraints(self, row: int, col: int) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        try:
            row = int(row)
            col = int(col)
        except (TypeError, ValueError):
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "row and col must be integers")

        try:
            from data_generation.validation import validate_slot_constraints
        except ImportError:
            from validation import validate_slot_constraints  # type: ignore

        _, slot, slot_error = self._get_slot(row, col)
        if slot_error is not None:
            return slot_error
        if not slot.get("is_hidden"):
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "Slot constraint checks are only allowed for hidden slots.",
            )
        if self.current_task.agent_solution[row][col] is None:
            return Messages.build_success_message({
                "row": row,
                "col": col,
                "is_valid": None,
                "reason": "This hidden slot is still empty, so it cannot be checked yet.",
            })

        is_valid, reason = validate_slot_constraints(
            solution=self.current_task.agent_solution,
            domain=dataset.domain,
            row_index=row,
            col_index=col,
            slot_constraint=slot["slot_constraints"],
            item_pool=dataset.item_pool,
            slots=dataset.slots,
            truth_solution=dataset.truth_solution,
        )
        return Messages.build_success_message({
            "row": row,
            "col": col,
            "is_valid": is_valid,
            "reason": reason,
        })

    def _check_global_constraints(self) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        solution = self.current_task.agent_solution
        if any(item_id is None for row in solution for item_id in row):
            return Messages.build_success_message({
                "is_valid": False,
                "reason": "The current grid is not fully filled yet.",
            })

        try:
            from data_generation.validation import validate_global_constraints
        except ImportError:
            from validation import validate_global_constraints  # type: ignore

        is_valid, reason = validate_global_constraints(
            solution=solution,
            domain=dataset.domain,
            global_constraints=dataset.global_constraints,
            item_pool=dataset.item_pool,
            slots=dataset.slots,
            truth_solution=dataset.truth_solution,
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
        dataset = task.dataset_object
        hidden_slot = next(
            (slot for slot in dataset.slots if slot.get("row") == row and slot.get("col") == col),
            None,
        )
        if hidden_slot is None:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"Slot (row={row}, col={col}) is fixed and cannot be modified",
            )
        slot_index = task.get_hidden_slot_index(row, col)
        normalized_id = str(id) if id is not None and id != "" else None
        current_target = task.get_current_target_slot()
        previous_target = task.get_previous_target_slot()

        if normalized_id is None:
            if current_target is not None and slot_index == current_target["index"] and solution[row][col] is None:
                return Messages.build_failure_message(
                    ErrorType.INVALID_ARGUMENTS,
                    (
                        f"Slot (row={row}, col={col}) is already empty. "
                        "Please provide a concrete id for the current hidden slot, or clear the immediately previous hidden slot instead."
                    ),
                )
            if previous_target is not None and slot_index == previous_target["index"]:
                solution[row][col] = None
                task.rollback_to_slot(row, col)
                return Messages.build_success_message(
                    {
                        "row": row,
                        "col": col,
                        "id": solution[row][col],
                        "message": "Previous hidden slot cleared. Rolled back to that slot.",
                        "current_slot": task.get_current_target_slot(),
                    }
                )
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    f"Slot (row={row}, col={col}) cannot be cleared. "
                    "You may only clear the immediately previous hidden slot."
                ),
            )

        access_error = self._ensure_hidden_slot_access(row, col)
        if access_error is not None:
            return access_error

        if current_target is None:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "There is no current hidden slot to fill.",
            )

        if current_target is None or slot_index != current_target["index"]:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    f"Slot (row={row}, col={col}) is not the current target slot. "
                    "Only the current hidden slot can be assigned a new id."
                ),
            )
        allowed_ids = {hidden_slot.get("truth_id"), *hidden_slot.get("decoy_ids", [])}
        if normalized_id not in allowed_ids:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    f"Slot (row={row}, col={col}) can only be set to its truth/decoy candidates. "
                    f"Allowed ids: {sorted(item_id for item_id in allowed_ids if item_id)}"
                ),
            )

        solution[row][col] = normalized_id
        task.advance_after_current_slot_fill(row, col)
        return Messages.build_success_message(
            {
                "row": row,
                "col": col,
                "id": solution[row][col],
                "message": "Current hidden slot completed.",
                "current_slot": task.get_current_target_slot(),
            }
        )

    def get_current_grid_state(self) -> Messages:
        """Return the full current grid state."""
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return Messages.build_success_message({"slots": task.agent_solution})

    def get_current_target_slot(self) -> Messages:
        """Get the current hidden slot position."""
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return Messages.build_success_message(
            {
                "current_slot": task.get_current_target_slot(),
            }
        )

    def get_previous_target_slot(self) -> Messages:
        """Get the previous hidden slot position."""
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return Messages.build_success_message(
            {
                "previous_slot": task.get_previous_target_slot(),
            }
        )

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
