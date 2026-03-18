"""PC build 领域的 tools。"""

from .. import BaseToolsHandler
from ..base import Messages


class PcBuildToolsHandler(BaseToolsHandler):
    """PC build 领域工具总 handler。"""

    domain = "pc_build"

    def __init__(self):
        super().__init__()
        self.tools.update({
            "query_pc_build_slot_candidates": self.query_pc_build_slot_candidates,
            "get_pc_build_item_info": self.get_pc_build_item_info,
            "get_pc_build_item_attributes": self.get_pc_build_item_attributes,
            "check_pc_build_slot_constraints": self.check_pc_build_slot_constraints,
            "check_pc_build_global_constraints": self.check_pc_build_global_constraints,
        })

    def query_pc_build_slot_candidates(self, row: int, col: int) -> Messages:
        """Return candidate ids, names, and categories for a PC build slot.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._query_slot_candidates(row, col, summary_fields=["name", "category"])

    def get_pc_build_item_info(self, id: str) -> Messages:
        """Return full PC build item information for one id.

        id: PC build item id as a string.
        """
        return self._get_item_info(id)

    def get_pc_build_item_attributes(self, ids: list[str], field: str | list[str]) -> Messages:
        """Return selected attribute value(s) for a batch of PC build item ids.

        ids: List of PC build item ids as strings, up to the current task limit.
        field: Attribute name(s) to retrieve. A string for one attribute, or a list within the current task limit.
        """
        return self._get_item_attribute_values(ids, field)

    def check_pc_build_slot_constraints(self, row: int, col: int) -> Messages:
        """Check whether a hidden slot satisfies its slot constraints.

        row: Row index as an integer.
        col: Column index as an integer.
        """
        return self._check_slot_constraints(row, col)

    def check_pc_build_global_constraints(self) -> Messages:
        """Check whether the current PC build grid satisfies the global constraints."""
        return self._check_global_constraints()
