import json
import random
from numbers import Number
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
            "get_hidden_slot_query_budget": self.get_hidden_slot_query_budget,
            "get_global_check_budget": self.get_global_check_budget,
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

    def _allowed_item_fields(self, dataset: Any) -> list[str]:
        if not getattr(dataset, "item_pool", None):
            return []
        sample_item = next(iter(dataset.item_pool.values()), None)
        if not isinstance(sample_item, dict):
            return []
        id_key = getattr(dataset, "domain", None)
        if id_key is not None:
            try:
                from data_generation.domains import DOMAIN_SPECS
            except ImportError:
                from domains import DOMAIN_SPECS  # type: ignore
            resolved_id_key = DOMAIN_SPECS[dataset.domain]["id_key"]
        else:
            resolved_id_key = "id"
        return sorted(key for key in sample_item.keys() if key != resolved_id_key)

    def _build_check_response(
        self,
        *,
        is_valid: bool | None,
        reason: str | None = None,
        row: int | None = None,
        col: int | None = None,
    ) -> Messages:
        task = self.current_task
        include_reason = False if task is None else task.check_include_reason
        payload: dict[str, Any] = {"is_valid": is_valid}
        if row is not None:
            payload["row"] = row
        if col is not None:
            payload["col"] = col
        if include_reason:
            payload["reason"] = reason
        return Messages.build_success_message(payload)

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

        return allowed_ids, None

    def _parse_query_value(self, value: Any, operator: str) -> tuple[Any, Messages | None]:
        if operator in {"in", "not_in"}:
            if isinstance(value, str):
                stripped_value = value.strip()
                if stripped_value.startswith("["):
                    try:
                        value = json.loads(stripped_value)
                    except json.JSONDecodeError:
                        value = [value]
                else:
                    value = [value]
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                return None, Messages.build_failure_message(
                    ErrorType.INVALID_ARGUMENTS,
                    "value must be a string list for `in` or `not_in` queries",
                )
            return value, None
        if isinstance(value, bool):
            return None, Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "boolean values are not supported for attribute queries",
            )
        if isinstance(value, Number):
            return value, None
        if isinstance(value, str):
            try:
                if "." in value:
                    return float(value), None
                return int(value), None
            except ValueError:
                return value, None
        return None, Messages.build_failure_message(
            ErrorType.INVALID_ARGUMENTS,
            "value must be numeric for numeric comparisons, or a string list for `in`/`not_in`",
        )

    def _query_candidate_from_attribute(
        self,
        row: int,
        col: int,
        field: str,
        operator: str,
        value: Any,
    ) -> Messages:
        dataset, slot, error = self._get_slot(row, col)
        if error is not None:
            return error
        if not slot.get("is_hidden"):
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "Attribute candidate queries are only allowed for hidden slots.",
            )
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        if not task.can_call_hidden_slot_query(slot["row"], slot["col"]):
            remaining_budget = task.get_remaining_hidden_slot_queries(slot["row"], slot["col"])
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    f"Hidden slot query budget exhausted for slot (row={slot['row']}, col={slot['col']}). "
                    f"Remaining queries: {remaining_budget}."
                ),
            )
        if not isinstance(field, str) or not field.strip():
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "field must be a non-empty string",
            )
        field = field.strip()
        allowed_fields = self._allowed_item_fields(dataset)
        if field not in allowed_fields:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "unknown field: "
                + field
                + ". allowed fields: "
                + ", ".join(allowed_fields),
            )
        if operator not in {">", ">=", "=", "<", "<=", "in", "not_in"}:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "operator must be one of: >, >=, =, <, <=, in, not_in",
            )
        candidate_ids = list(slot.get("candidate_ids", []))
        sample_value = None
        for item_id in candidate_ids:
            item = dataset.item_pool.get(item_id)
            if item is not None and field in item:
                sample_value = item[field]
                break
        if sample_value is None:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"field `{field}` is not available on the current slot candidates",
            )
        parsed_value, value_error = self._parse_query_value(value, operator)
        if value_error is not None:
            return value_error
        is_numeric_field = isinstance(sample_value, Number) and not isinstance(sample_value, bool)
        if is_numeric_field and operator in {"in", "not_in"}:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "numeric fields only support: >, >=, =, <, <=",
            )
        if not is_numeric_field and operator not in {"in", "not_in"}:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "categorical fields only support: in, not_in",
            )
        matches = []
        for item_id in candidate_ids:
            item = dataset.item_pool.get(item_id)
            if item is None or field not in item:
                continue
            observed = item[field]
            matched = False
            if is_numeric_field:
                if not isinstance(parsed_value, Number) or isinstance(parsed_value, bool):
                    return Messages.build_failure_message(
                        ErrorType.INVALID_ARGUMENTS,
                        "numeric comparisons require a numeric value",
                    )
                if operator == ">":
                    matched = observed > parsed_value
                elif operator == ">=":
                    matched = observed >= parsed_value
                elif operator == "=":
                    matched = observed == parsed_value
                elif operator == "<":
                    matched = observed < parsed_value
                elif operator == "<=":
                    matched = observed <= parsed_value
            else:
                assert isinstance(parsed_value, list)
                if operator == "in":
                    matched = observed in parsed_value
                elif operator == "not_in":
                    matched = observed not in parsed_value
            if matched:
                matches.append({"id": item_id, field: observed})
        task.record_hidden_slot_query_call(slot["row"], slot["col"])
        return Messages.build_success_message(
            {
                "row": slot["row"],
                "col": slot["col"],
                "field": field,
                "operator": operator,
                "value": parsed_value,
                "matches": matches,
                "remaining_budget": task.get_remaining_hidden_slot_queries(slot["row"], slot["col"]),
            }
        )

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
                    "You may only inspect ids from non-hidden slots."
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
                    + ". You may only inspect ids from non-hidden slots."
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
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                f"Slot (row={row}, col={col}) has not been filled yet.",
            )

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
        return self._build_check_response(
            row=row,
            col=col,
            is_valid=is_valid,
            reason=reason,
        )

    def _check_global_constraints(self) -> Messages:
        dataset, error = self._get_current_dataset()
        if error is not None:
            return error
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        solution = self.current_task.agent_solution
        if any(item_id is None for row in solution for item_id in row):
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "The current grid must be fully filled before global constraints can be checked.",
            )
        if not task.can_call_global_check():
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    "Global constraint check budget exhausted. "
                    f"Used {task.global_check_calls}/{task.global_check_budget} calls."
                ),
            )
        task.record_global_check_call()

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
        return self._build_check_response(
            is_valid=is_valid,
            reason=reason,
        )

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
        normalized_id = str(id) if id is not None and id != "" else None
        if normalized_id is None:
            if solution[row][col] is None:
                return Messages.build_failure_message(
                    ErrorType.INVALID_ARGUMENTS,
                    f"Slot (row={row}, col={col}) is already empty.",
                )
            solution[row][col] = None
            return Messages.build_success_message(
                {
                    "row": row,
                    "col": col,
                    "id": None,
                    "message": "Hidden slot cleared.",
                }
            )
        allowed_ids = set(hidden_slot.get("candidate_ids", []))
        if normalized_id not in allowed_ids:
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                (
                    f"Slot (row={row}, col={col}) can only be set to one of its candidate ids. "
                    f"Allowed ids: {sorted(item_id for item_id in allowed_ids if item_id)}"
                ),
            )

        solution[row][col] = normalized_id
        return Messages.build_success_message(
            {
                "row": row,
                "col": col,
                "id": normalized_id,
                "message": "Hidden slot updated.",
            }
        )

    def get_current_grid_state(self) -> Messages:
        """Return the full current grid state."""
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return Messages.build_success_message({"slots": task.agent_solution})

    def get_hidden_slot_query_budget(self, row: int, col: int) -> Messages:
        """Get the remaining attribute-query budget for one hidden slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        _, slot, slot_error = self._get_slot(row, col)
        if slot_error is not None:
            return slot_error
        if not slot.get("is_hidden"):
            return Messages.build_failure_message(
                ErrorType.INVALID_ARGUMENTS,
                "Hidden-slot query budget is only available for hidden slots.",
            )
        return Messages.build_success_message(
            {
                "row": slot["row"],
                "col": slot["col"],
                "query_budget": task.hidden_slot_query_budget.get((slot["row"], slot["col"]), 0),
                "query_calls": task.hidden_slot_query_calls.get((slot["row"], slot["col"]), 0),
                "remaining_queries": task.get_remaining_hidden_slot_queries(slot["row"], slot["col"]),
            }
        )

    def get_global_check_budget(self) -> Messages:
        """Get the remaining global-check budget."""
        task = self.current_task
        if task is None:
            return Messages.build_failure_message(ErrorType.INVALID_ARGUMENTS, "No current task")
        return Messages.build_success_message(task.get_global_check_budget_status())

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
