"""Workforce scheduling 领域的 tools。"""

from .. import BaseToolsHandler
from ..base import Messages


class WorkforceToolsHandler(BaseToolsHandler):
    """Workforce 领域工具总 handler。"""

    domain = "workforce"

    def __init__(self):
        super().__init__()
        self.tools.update({
            "query_workforce_slot_candidates": self.query_workforce_slot_candidates,
            "get_workforce_item_info": self.get_workforce_item_info,
            "get_workforce_item_attributes": self.get_workforce_item_attributes,
            "check_workforce_slot_constraints": self.check_workforce_slot_constraints,
            "check_workforce_global_constraints": self.check_workforce_global_constraints,
        })

    def query_workforce_slot_candidates(self, row: int, col: int) -> Messages:
        """Return candidate ids, names, and departments for a workforce slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._query_slot_candidates(row, col, summary_fields=["name", "department"])

    def get_workforce_item_info(self, id: str) -> Messages:
        """Return full workforce item information for one id.

        id: Workforce item id as a string.
        """
        return self._get_item_info(id)

    def get_workforce_item_attributes(self, ids: list[str], field: str | list[str]) -> Messages:
        """Return selected attribute value(s) for a batch of workforce item ids.

        ids: List of workforce item ids as strings, up to the current task limit.
        field: Attribute name(s) to retrieve. A string for one attribute, or a list within the current task limit.
        """
        return self._get_item_attribute_values(ids, field)

    def check_workforce_slot_constraints(self, row: int, col: int) -> Messages:
        """Check whether a hidden slot satisfies its slot constraints.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._check_slot_constraints(row, col)

    def check_workforce_global_constraints(self) -> Messages:
        """Check whether the current workforce grid satisfies the global constraints."""
        return self._check_global_constraints()
