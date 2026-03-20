"""Travel itinerary 领域的 tools。"""

from .. import BaseToolsHandler
from ..base import Messages


class TravelToolsHandler(BaseToolsHandler):
    """Travel 领域工具总 handler。"""

    domain = "travel"

    def __init__(self):
        super().__init__()
        self.tools.update({
            "query_travel_candidate_from_attribute": self.query_travel_candidate_from_attribute,
            "get_travel_item_info": self.get_travel_item_info,
            "get_travel_item_attributes": self.get_travel_item_attributes,
            "check_travel_slot_constraints": self.check_travel_slot_constraints,
            "check_travel_global_constraints": self.check_travel_global_constraints,
        })

    def query_travel_candidate_from_attribute(
        self,
        row: int,
        col: int,
        field: str,
        operator: str,
        value: str | int | float | list[str],
    ) -> Messages:
        """Filter current-slot travel candidates by one attribute condition.

        row: Row index as an integer.
        col: Column index as an integer.
        field: One attribute name to filter on.
        operator: For numeric fields use one of `>`, `>=`, `=`, `<`, `<=`; for categorical fields use `in` or `not_in`.
        value: One numeric comparison value, or a string list for `in`/`not_in`.
        """
        return self._query_candidate_from_attribute(row, col, field, operator, value)

    def get_travel_item_info(self, id: str) -> Messages:
        """Return full travel item information for one id.

        id: Travel item id as a string.
        """
        return self._get_item_info(id)

    def get_travel_item_attributes(self, ids: list[str], field: str | list[str]) -> Messages:
        """Return selected attribute value(s) for a batch of travel item ids.

        ids: List of travel item ids as strings, up to the current task limit.
        field: Attribute name(s) to retrieve. A string for one attribute, or a list within the current task limit.
        """
        return self._get_item_attribute_values(ids, field)

    def check_travel_slot_constraints(self, row: int, col: int) -> Messages:
        """Check whether a hidden slot satisfies its slot constraints.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._check_slot_constraints(row, col)

    def check_travel_global_constraints(self) -> Messages:
        """Check whether the current travel grid satisfies the global constraints."""
        return self._check_global_constraints()
