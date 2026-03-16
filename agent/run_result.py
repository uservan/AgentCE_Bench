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
        self.status = status
        self.reason = reason

    def set_score(self, score: Any):
        self.usage["score"] = score

    @property
    def score(self):
        return self.usage.get("score")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "content": self.content,
            "usage": self.usage,
            "raw_messages": self.raw_messages,
            "score": self.score,
        }
