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
            "check_pc_build_row_constraints": self.check_pc_build_row_constraints,
            "check_pc_build_col_constraints": self.check_pc_build_col_constraints,
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

    def get_pc_build_item_attributes(self, ids: list[str], field: str) -> Messages:
        """Return one selected attribute value for up to five PC build item ids.

        ids: List of PC build item ids as strings, with at most 5 items.
        field: Attribute name to retrieve for each PC build item.
        """
        return self._get_item_attribute_values(ids, field, max_items=5)

    def check_pc_build_row_constraints(self, row: int) -> Messages:
        """Check whether a row satisfies the PC build row constraints.

        row: Row index as an integer.
        """
        return self._check_row_constraints(row)

    def check_pc_build_col_constraints(self, col: int) -> Messages:
        """Check whether a column satisfies the PC build column constraints.

        col: Column index as an integer.
        """
        return self._check_col_constraints(col)

    def check_pc_build_global_constraints(self) -> Messages:
        """Check whether the current PC build grid satisfies the global constraints."""
        return self._check_global_constraints()
