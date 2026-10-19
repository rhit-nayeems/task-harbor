from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    UNPLANNED = "UNPLANNED"
    PLANNING = "PLANNING"
    PLAN_REVIEW = "PLAN_REVIEW"
    READY = "READY"
    IMPLEMENTING = "IMPLEMENTING"
    QA = "QA"
    QA_FAIL = "QA_FAIL"
    QA_PASSED = "QA_PASSED"
    CODE_REVIEW = "CODE_REVIEW"
    COMPLETE = "COMPLETE"


class Priority(StrEnum):
    BLOCKER = "blocker"
    CRITICAL_BUG = "critical_bug"
    HIGH_RISK = "high_risk"
    CORE = "core"
    LOW_RISK = "low_risk"
    POLISH = "polish"


PRIORITY_ORDER = {
    Priority.BLOCKER: 0,
    Priority.CRITICAL_BUG: 1,
    Priority.HIGH_RISK: 2,
    Priority.CORE: 3,
    Priority.LOW_RISK: 4,
    Priority.POLISH: 5,
}


@dataclass
class BacklogTask:
    task_id: str
    title: str
    priority: Priority = Priority.CORE
    status: TaskStatus = TaskStatus.UNPLANNED
    owner: str | None = None
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    next_action: str = ""
    blocked_reason: str | None = None
    plan_path: str | None = None
    plan_base_commit: str | None = None
    plan_reworks: int = 0
    implementer_session_id: str | None = None
    worktree_path: str | None = None
    branch_name: str | None = None
    checkpoint_commit: str | None = None
    last_qa_path: str | None = None
    qa_failures: int = 0
    generation: int = 0
    last_error: str | None = None
    completed_commit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BacklogTask":
        x = dict(d)
        x["priority"] = Priority(x.get("priority", Priority.CORE))
        x["status"] = TaskStatus(x.get("status", TaskStatus.UNPLANNED))
        return cls(**x)


@dataclass
class ManagerState:
    run_id: str
    repo: str
    integration_branch: str
    integration_worktree: str
    base_branch: str
    base_commit: str
    tasks: dict[str, BacklogTask] = field(default_factory=dict)
    qa_passes_since_review: int = 0
    last_review_commit: str | None = None
    active_planners: list[str] = field(default_factory=list)
    event_seq: int = 0
    paused: bool = False
    stop_reason: str | None = None
    schema_version: int = 3
    provider: str = "claude"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tasks"] = {k: v.to_dict() for k, v in self.tasks.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ManagerState":
        x = dict(d)
        x["tasks"] = {k: BacklogTask.from_dict(v) for k, v in x.get("tasks", {}).items()}
        return cls(**x)
