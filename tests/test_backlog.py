from pathlib import Path

import pytest

from opus_manager.backlog import parse_backlog, render_backlog
from opus_manager.models import BacklogTask, Priority, TaskStatus
from opus_manager.orchestrator import ManagerError, validate_tasks


def test_backlog_roundtrip(tmp_path: Path):
    p = tmp_path / "BACKLOG.md"
    tasks = {
        "T-1": BacklogTask(
            task_id="T-1",
            title="First",
            priority=Priority.CRITICAL_BUG,
            status=TaskStatus.READY,
            dependencies=[],
            acceptance_criteria=["Tests pass", "Bug no longer reproduces"],
            next_action="Implement",
        ),
        "T-2": BacklogTask(
            task_id="T-2",
            title="Second",
            dependencies=["T-1"],
            acceptance_criteria=["Feature works"],
        ),
    }
    render_backlog(p, tasks)
    parsed = parse_backlog(p)
    assert parsed["T-1"].priority == Priority.CRITICAL_BUG
    assert parsed["T-1"].acceptance_criteria == ["Tests pass", "Bug no longer reproduces"]
    assert parsed["T-2"].dependencies == ["T-1"]


def test_dependency_validation_rejects_cycle():
    tasks = {
        "A": BacklogTask("A", "A", dependencies=["B"], acceptance_criteria=["x"]),
        "B": BacklogTask("B", "B", dependencies=["A"], acceptance_criteria=["x"]),
    }
    with pytest.raises(ManagerError, match="dependency cycle"):
        validate_tasks(tasks)


def test_dependency_validation_rejects_unknown():
    tasks = {"A": BacklogTask("A", "A", dependencies=["MISSING"], acceptance_criteria=["x"])}
    with pytest.raises(ManagerError, match="unknown dependency"):
        validate_tasks(tasks)


def test_write_template_is_parseable(tmp_path: Path):
    from opus_manager.backlog import write_template
    p = tmp_path / "BACKLOG.md"
    write_template(p)
    parsed = parse_backlog(p)
    assert "TASK-001" in parsed
    assert parsed["TASK-001"].acceptance_criteria


def test_duplicate_task_ids_are_rejected(tmp_path: Path):
    p = tmp_path / "BACKLOG.md"
    p.write_text("""# Backlog

## SAME — First
- **Acceptance criteria:**
  - first works

## SAME — Second
- **Acceptance criteria:**
  - second works
""", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate backlog task ID"):
        parse_backlog(p)
