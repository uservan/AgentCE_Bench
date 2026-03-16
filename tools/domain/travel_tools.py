"""Travel itinerary 领域的 tools。"""

from .. import BaseToolsHandler
from ..base import Messages


class TravelToolsHandler(BaseToolsHandler):
    """Travel 领域工具总 handler。"""

    domain = "travel"

    def __init__(self):
        super().__init__()
        self.tools.update({
            "query_travel_slot_candidates": self.query_travel_slot_candidates,
            "get_travel_item_info": self.get_travel_item_info,
            "get_travel_item_attributes": self.get_travel_item_attributes,
            "check_travel_row_constraints": self.check_travel_row_constraints,
            "check_travel_col_constraints": self.check_travel_col_constraints,
            "check_travel_global_constraints": self.check_travel_global_constraints,
        })

    def query_travel_slot_candidates(self, row: int, col: int) -> Messages:
        """Return candidate ids, names, and categories for a travel slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._query_slot_candidates(row, col, summary_fields=["name", "category"])

    def get_travel_item_info(self, id: str) -> Messages:
        """Return full travel item information for one id.

        id: Travel item id as a string.
        """
        return self._get_item_info(id)

    def get_travel_item_attributes(self, ids: list[str], field: str) -> Messages:
        """Return one selected attribute value for up to five travel item ids.

        ids: List of travel item ids as strings, with at most 5 items.
        field: Attribute name to retrieve for each travel item.
        """
        return self._get_item_attribute_values(ids, field, max_items=5)

    def check_travel_row_constraints(self, row: int) -> Messages:
        """Check whether a row satisfies the travel row constraints.

        row: Row index as an integer.
        """
        return self._check_row_constraints(row)

    def check_travel_col_constraints(self, col: int) -> Messages:
        """Check whether a column satisfies the travel column constraints.

        col: Column index as an integer.
        """
        return self._check_col_constraints(col)

    def check_travel_global_constraints(self) -> Messages:
        """Check whether the current travel grid satisfies the global constraints."""
        return self._check_global_constraints()
