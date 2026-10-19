from __future__ import annotations

import re
from pathlib import Path

from .models import BacklogTask, Priority, TaskStatus

TASK_RE = re.compile(r"^##\s+([A-Za-z0-9_.-]+)\s*[—-]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(.+?):\*\*\s*(.*?)\s*$")


def _split_csv(value: str) -> list[str]:
    value = value.strip()
    if not value or value in {"—", "-", "none", "None", "[]"}:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def parse_backlog(path: Path) -> dict[str, BacklogTask]:
    if not path.exists():
        raise FileNotFoundError(f"Backlog not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    tasks: dict[str, BacklogTask] = {}
    i = 0
    while i < len(lines):
        m = TASK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        task_id, title = m.group(1), m.group(2)
        if task_id in tasks:
            raise ValueError(f"Duplicate backlog task ID: {task_id}")
        fields: dict[str, str] = {}
        criteria: list[str] = []
        i += 1
        in_criteria = False
        while i < len(lines) and not TASK_RE.match(lines[i]):
            line = lines[i]
            fm = FIELD_RE.match(line)
            if fm:
                key = fm.group(1).strip().lower().replace(" ", "_")
                val = fm.group(2).strip()
                fields[key] = val
                in_criteria = key == "acceptance_criteria"
            elif in_criteria:
                cm = re.match(r"^\s{2,}-\s+(.*)$", line)
                if cm:
                    criteria.append(cm.group(1).strip())
                elif line.strip():
                    in_criteria = False
            i += 1
        try:
            priority = Priority(fields.get("priority", "core").lower())
        except ValueError as e:
            raise ValueError(f"{task_id}: invalid priority {fields.get('priority')!r}") from e
        try:
            status = TaskStatus(fields.get("status", "UNPLANNED").upper())
        except ValueError as e:
            raise ValueError(f"{task_id}: invalid status {fields.get('status')!r}") from e
        owner = fields.get("owner") or None
        if owner in {"—", "-", "none", "None"}:
            owner = None
        blocked_reason = fields.get("blocked_reason") or None
        if blocked_reason in {"—", "-", "none", "None"}:
            blocked_reason = None
        tasks[task_id] = BacklogTask(
            task_id=task_id,
            title=title,
            priority=priority,
            status=status,
            owner=owner,
            dependencies=_split_csv(fields.get("dependencies", "")),
            acceptance_criteria=criteria,
            next_action=fields.get("next_action", ""),
            blocked_reason=blocked_reason,
            plan_path=(fields.get("plan") or None),
        )
    if not tasks:
        raise ValueError(f"No tasks found in {path}. Use the documented BACKLOG.md format.")
    return tasks


def render_backlog(path: Path, tasks: dict[str, BacklogTask]) -> None:
    parts = [
        "# Backlog",
        "",
        "> Managed by Task Harbor. Edit task intent/priority/dependencies/acceptance criteria when needed; runtime fields are synchronized by the manager.",
        "",
    ]
    for t in tasks.values():
        parts.extend([
            f"## {t.task_id} — {t.title}",
            f"- **Priority:** {t.priority.value}",
            f"- **Status:** {t.status.value}",
            f"- **Owner:** {t.owner or '—'}",
            f"- **Dependencies:** {', '.join(t.dependencies) if t.dependencies else '—'}",
            f"- **Blocked reason:** {t.blocked_reason or '—'}",
            f"- **Plan:** {t.plan_path or '—'}",
            "- **Acceptance criteria:**",
        ])
        if t.acceptance_criteria:
            parts.extend([f"  - {c}" for c in t.acceptance_criteria])
        else:
            parts.append("  - Define acceptance criteria")
        parts.extend([
            f"- **Next action:** {t.next_action or '—'}",
            "",
        ])
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_template(path: Path) -> None:
    path.write_text(
        """# Backlog

## TASK-001 — Replace this with real work
- **Priority:** core
- **Status:** UNPLANNED
- **Owner:** —
- **Dependencies:** —
- **Blocked reason:** —
- **Plan:** —
- **Acceptance criteria:**
  - Define an observable success condition
- **Next action:** Plan the task
""",
        encoding="utf-8",
    )
