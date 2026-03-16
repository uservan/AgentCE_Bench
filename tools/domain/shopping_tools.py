"""Grocery shopping 领域的 tools。"""

from .. import BaseToolsHandler
from ..base import Messages


class ShoppingToolsHandler(BaseToolsHandler):
    """Shopping 领域工具总 handler。"""

    domain = "shopping"

    def __init__(self):
        super().__init__()
        self.tools.update({
            "query_shopping_slot_candidates": self.query_shopping_slot_candidates,
            "get_shopping_item_info": self.get_shopping_item_info,
            "get_shopping_item_attributes": self.get_shopping_item_attributes,
            "check_shopping_row_constraints": self.check_shopping_row_constraints,
            "check_shopping_col_constraints": self.check_shopping_col_constraints,
            "check_shopping_global_constraints": self.check_shopping_global_constraints,
        })

    def query_shopping_slot_candidates(self, row: int, col: int) -> Messages:
        """Return candidate ids, names, and categories for a shopping slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._query_slot_candidates(row, col, summary_fields=["name", "category"])

    def get_shopping_item_info(self, id: str) -> Messages:
        """Return full shopping item information for one id.

        id: Shopping item id as a string.
        """
        return self._get_item_info(id)

    def get_shopping_item_attributes(self, ids: list[str], field: str) -> Messages:
        """Return one selected attribute value for up to five shopping item ids.

        ids: List of shopping item ids as strings, with at most 5 items.
        field: Attribute name to retrieve for each shopping item.
        """
        return self._get_item_attribute_values(ids, field, max_items=5)

    def check_shopping_row_constraints(self, row: int) -> Messages:
        """Check whether a row satisfies the shopping row constraints.

        row: Row index as an integer.
        """
        return self._check_row_constraints(row)

    def check_shopping_col_constraints(self, col: int) -> Messages:
        """Check whether a column satisfies the shopping column constraints.

        col: Column index as an integer.
        """
        return self._check_col_constraints(col)

    def check_shopping_global_constraints(self) -> Messages:
        """Check whether the current shopping grid satisfies the global constraints."""
        return self._check_global_constraints()
