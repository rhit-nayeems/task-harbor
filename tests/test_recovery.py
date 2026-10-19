from pathlib import Path

import pytest

from opus_manager.config import Config
from opus_manager.models import BacklogTask, ManagerState, TaskStatus
from opus_manager.orchestrator import ManagerError, Orchestrator


def make_manager(tmp_path: Path, tasks: dict[str, BacklogTask]) -> Orchestrator:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    integration = tmp_path / "integration"
    integration.mkdir()
    state = ManagerState(
        run_id="recovery",
        repo=str(repo),
        integration_branch="manager/integration/recovery",
        integration_worktree=str(integration),
        base_branch="main",
        base_commit="base",
        tasks=tasks,
    )
    return Orchestrator(repo, Config(), "recovery", state=state)


def test_resume_recovers_inflight_states_to_idempotent_work(tmp_path: Path):
    tasks = {
        "PLAN": BacklogTask("PLAN", "Planning", status=TaskStatus.PLANNING),
        "IMPL": BacklogTask("IMPL", "Implementing", status=TaskStatus.IMPLEMENTING),
        "QA": BacklogTask("QA", "QA", status=TaskStatus.QA, checkpoint_commit="checkpoint"),
        "FAIL": BacklogTask("FAIL", "Failed", status=TaskStatus.QA_FAIL, qa_failures=1),
        "PASS": BacklogTask("PASS", "Passed", status=TaskStatus.QA_PASSED, checkpoint_commit="checkpoint"),
    }
    manager = make_manager(tmp_path, tasks)

    manager._recover_interrupted_tasks()

    assert tasks["PLAN"].status == TaskStatus.UNPLANNED
    assert tasks["IMPL"].metadata["resume_mode"] == "implementation"
    assert tasks["QA"].metadata["resume_mode"] == "qa"
    assert tasks["FAIL"].metadata["resume_mode"] == "repair"
    assert tasks["PASS"].metadata["resume_mode"] == "merge"
    assert all(t.status in {TaskStatus.UNPLANNED, TaskStatus.READY} for t in tasks.values())


def test_operational_block_survives_dependency_refresh(tmp_path: Path):
    task = BacklogTask(
        "T", "Task", acceptance_criteria=["works"],
        blocked_reason="Plan rework limit reached; manager intervention required",
        metadata={"blocked_kind": "plan_rework_limit"},
    )
    manager = make_manager(tmp_path, {"T": task})

    manager._refresh_blocking()

    assert task.blocked_reason == "Plan rework limit reached; manager intervention required"
    assert task.metadata["blocked_kind"] == "plan_rework_limit"


def test_qa_pass_counter_is_idempotent_per_checkpoint(tmp_path: Path):
    task = BacklogTask("T", "Task")
    manager = make_manager(tmp_path, {"T": task})

    manager._count_qa_pass(task, "abc")
    manager._count_qa_pass(task, "abc")
    manager._count_qa_pass(task, "def")

    assert manager.state.qa_passes_since_review == 2


def test_blocking_review_finding_overrides_optimistic_pass(tmp_path: Path):
    manager = make_manager(tmp_path, {})
    review = {
        "verdict": "PASS",
        "findings": [{"severity": "BUG", "title": "Still broken"}],
    }
    assert manager._review_requires_changes(review)


def test_task_qa_pass_requires_evidence_for_every_criterion(tmp_path: Path):
    task = BacklogTask("T", "Task", acceptance_criteria=["one", "two"])
    manager = make_manager(tmp_path, {"T": task})
    result = {
        "verdict": "PASS",
        "summary": "looks good",
        "acceptance": [{"criterion": "one", "status": "PASS", "evidence": "test one"}],
        "failures": [],
    }

    manager._normalize_task_qa(task, result)

    assert result["verdict"] == "UNVERIFIED"
    assert result["failures"]


def test_malformed_review_payload_fails_closed(tmp_path: Path):
    manager = make_manager(tmp_path, {})
    assert manager._review_requires_changes({"verdict": "PASS", "findings": None})


def test_only_one_process_can_hold_a_run_lock(tmp_path: Path):
    first = make_manager(tmp_path / "first", {})
    second = Orchestrator(first.repo, first.config, "recovery", state=first.state)
    first._acquire_run_lock()
    try:
        with pytest.raises(ManagerError, match="already active"):
            second._acquire_run_lock()
    finally:
        first._release_run_lock()
