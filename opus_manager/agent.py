"""Provider-neutral result and error types."""
from dataclasses import dataclass
from typing import Any


class AgentError(RuntimeError):
    def __init__(self, message: str, raw: dict | None = None):
        super().__init__(message)
        self.raw = raw


@dataclass
class AgentResult:
    text: str
    session_id: str | None
    raw: dict[str, Any]
    returncode: int
