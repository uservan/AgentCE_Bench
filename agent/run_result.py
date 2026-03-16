import copy
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .task import Task


class RunResult:
    """单次 run 的结果。"""

    def __init__(
        self,
        task: "Task",
        content: Any,
        usage: Optional[dict[str, Any]] = None,
        raw_messages: Optional[list[dict[str, Any]]] = None,
        status: str = "succeed",
        reason: Optional[str] = None,
    ):
        self.task = task
        self.content = content
        self.usage = usage or {}
        self.raw_messages = raw_messages or []
        self.result: Optional[dict[str, Any]] = None
        self.score: Optional[int] = None
        self.status = status
        self.reason = reason

    def set_result(self, result: dict[str, Any]):
        enriched_result = copy.deepcopy(result)
        enriched_result["initial_solution"] = copy.deepcopy(self.task.partial_solution)
        enriched_result["agent_solution"] = copy.deepcopy(self.task.agent_solution)
        enriched_result["truth_solution"] = copy.deepcopy(self.task.dataset_object.truth_solution)
        self.result = enriched_result
        self.score = self._score_from_result(enriched_result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "content": self.content,
            "usage": self.usage,
            "raw_messages": self.raw_messages,
            "result": self.result,
            "score": self.score,
        }

    def _score_from_result(self, result: Optional[dict[str, Any]]) -> Optional[int]:
        if not isinstance(result, dict):
            return None
        value = result.get("score")
        if value is True:
            return 1
        if value is False:
            return 0
        return None
