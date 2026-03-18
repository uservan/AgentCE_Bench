"""Meal planning 领域的 tools。"""

from .. import BaseToolsHandler
from ..base import Messages


class MealToolsHandler(BaseToolsHandler):
    """Meal 领域工具总 handler。"""

    domain = "meal"

    def __init__(self):
        super().__init__()
        self.tools.update({
            "query_meal_slot_candidates": self.query_meal_slot_candidates,
            "get_meal_item_info": self.get_meal_item_info,
            "get_meal_item_attributes": self.get_meal_item_attributes,
            "check_meal_slot_constraints": self.check_meal_slot_constraints,
            "check_meal_global_constraints": self.check_meal_global_constraints,
        })

    def query_meal_slot_candidates(self, row: int, col: int) -> Messages:
        """Return candidate ids, names, and cuisines for a meal slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._query_slot_candidates(row, col, summary_fields=["name", "cuisine"])

    def get_meal_item_info(self, id: str) -> Messages:
        """Return full meal item information for one id.

        id: Meal item id as a string.
        """
        return self._get_item_info(id)

    def get_meal_item_attributes(self, ids: list[str], field: str | list[str]) -> Messages:
        """Return selected attribute value(s) for a batch of meal item ids.

        ids: List of meal item ids as strings, up to the current task limit.
        field: Attribute name(s) to retrieve. A string for one attribute, or a list within the current task limit.
        """
        return self._get_item_attribute_values(ids, field)

    def check_meal_slot_constraints(self, row: int, col: int) -> Messages:
        """Check whether a hidden slot satisfies its slot constraints.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._check_slot_constraints(row, col)

    def check_meal_global_constraints(self) -> Messages:
        """Check whether the current meal grid satisfies the global constraints."""
        return self._check_global_constraints()
