from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Config:
    model: str = "opus"
    effort: str = "medium"
    claude_bin: str = "claude"
    max_active_planners: int = 4
    max_fix_attempts_before_restart: int = 2
    max_fresh_implementer_generations: int = 3
    max_plan_reworks: int = 2
    max_code_review_fix_attempts: int = 2
    qa_passes_per_code_review: int = 3
    agent_timeout_seconds: int = 3600
    max_turns_manager: int = 12
    max_turns_planner: int = 30
    max_turns_implementer: int = 80
    max_turns_qa: int = 40
    max_turns_reviewer: int = 50
    max_turns_diagnosis: int = 50
    max_manager_cycles: int = 1000
    scheduler: str = "deterministic"
    final_code_review: bool = False
    max_agent_calls: int | None = None
    max_task_agent_calls: int | None = None
    max_run_cost_usd: float | None = None
    max_call_cost_usd: float | None = None
    verification_timeout_seconds: int = 300
    evidence_max_chars: int = 12000
    verification_commands: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=lambda: [
        ".git", ".manager", ".env", ".env.*", "**/.env", "**/.env.*",
        "*.pem", "*.key", "**/*.pem", "**/*.key", "secrets.*", "**/secrets.*"
    ])
    allow_dirty_repo: bool = False
    keep_task_worktrees: bool = True
    manager_dir: str = ".manager"
    backlog_file: str = "BACKLOG.md"
    integration_branch_prefix: str = "manager/integration"
    task_branch_prefix: str = "manager/task"

    def __post_init__(self) -> None:
        nonnegative = {"max_fix_attempts_before_restart", "max_plan_reworks", "max_code_review_fix_attempts"}
        for name, value in asdict(self).items():
            if name.startswith("max_turns_") or name in nonnegative | {
                "max_active_planners", "max_fresh_implementer_generations", "qa_passes_per_code_review",
                "agent_timeout_seconds", "max_manager_cycles", "verification_timeout_seconds", "evidence_max_chars",
            }:
                if type(value) is not int or value < (0 if name in nonnegative else 1):
                    raise ValueError(f"Invalid {name}: {value!r}")
        if self.max_active_planners > 4:
            raise ValueError("max_active_planners cannot exceed 4")
        if self.scheduler not in {"deterministic", "model"}:
            raise ValueError("scheduler must be deterministic or model")
        if self.max_agent_calls is not None and (type(self.max_agent_calls) is not int or self.max_agent_calls < 1):
            raise ValueError("max_agent_calls must be a positive integer")
        if self.max_task_agent_calls is not None and (type(self.max_task_agent_calls) is not int or self.max_task_agent_calls < 1):
            raise ValueError("max_task_agent_calls must be a positive integer")
        for name in ("max_run_cost_usd", "max_call_cost_usd"):
            value = getattr(self, name)
            if value is not None and (type(value) not in {int, float} or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be a positive finite number")
        for name in ("verification_commands", "protected_paths"):
            value = getattr(self, name)
            if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                raise ValueError(f"{name} must be a list of nonempty strings")
        for name in ("manager_dir", "backlog_file"):
            value = Path(getattr(self, name))
            if value.is_absolute() or ".." in value.parts or str(value) == ".":
                raise ValueError(f"{name} must be a relative path inside the repository")
        allowed_effort = {"low", "medium", "high", "xhigh", "max"}
        self.effort = self.effort.lower()
        if self.effort not in allowed_effort:
            raise ValueError(
                f"Invalid Claude effort {self.effort!r}; expected one of: "
                + ", ".join(sorted(allowed_effort))
            )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            cfg = cls()
            path.parent.mkdir(parents=True, exist_ok=True)
            cfg.save(path)
            return cfg
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in __import__("dataclasses").fields(cls)}
        cfg = cls(**{k: v for k, v in raw.items() if k in known})
        missing = known.difference(raw)
        if missing:
            # Migrate older config files when new settings gain defaults. Preserve
            # unknown keys so forward-compatible or locally managed settings are
            # not destroyed by an older manager version.
            migrated = dict(raw)
            migrated.update(asdict(cfg))
            path.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
        return cfg
