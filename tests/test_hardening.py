import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from opus_manager.config import Config
from opus_manager.models import BacklogTask, TaskStatus
from opus_manager.orchestrator import Orchestrator
from opus_manager.usage import RunStopped, UsageLedger, summarize
from opus_manager.verification import run_checks
from opus_manager.reporting import run_report, write_html
from opus_manager.cli import main
from test_recovery import make_manager
from test_orchestrator_integration import FakeClaude, init_repo


@pytest.mark.parametrize("values", [
    {"max_active_planners": 0}, {"max_active_planners": 5}, {"agent_timeout_seconds": -1},
    {"max_plan_reworks": -1}, {"qa_passes_per_code_review": 0}, {"max_agent_calls": True},
    {"max_run_cost_usd": float("nan")}, {"max_call_cost_usd": 0},
    {"scheduler": "random"}, {"verification_commands": "pytest"}, {"manager_dir": "../outside"},
])
def test_invalid_config(values):
    with pytest.raises(ValueError):
        Config(**values)


def test_parallel_reservations_obey_call_limit_and_survive_reload(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.json", Config(max_agent_calls=2))
    def reserve(_):
        try:
            return ledger.reserve("analysis", None)
        except RunStopped:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(8)))
    assert sum(r is not None for r in results) == 2
    reloaded = UsageLedger(ledger.path, ledger.config)
    with pytest.raises(RunStopped):
        reloaded.reserve("analysis", None)


def test_unknown_interrupted_cost_stays_reserved(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.json", Config(max_run_cost_usd=2, max_call_cost_usd=2))
    ledger.reserve("implementer", "T")
    with pytest.raises(RunStopped, match="cost budget"):
        UsageLedger(ledger.path, ledger.config).reserve("analysis", None)


def test_actual_cost_releases_unused_reservation(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.json", Config(max_run_cost_usd=2, max_call_cost_usd=2))
    call_id, _ = ledger.reserve("implementer", "T")
    ledger.finish(call_id, {"total_cost_usd": .25, "usage": {"input_tokens": 10}})
    _, cap = ledger.reserve("analysis", None)
    assert cap == 1.75
    assert summarize(ledger.read())["tokens"]["input_tokens"] == 10


def test_stop_request_prevents_new_calls(tmp_path):
    (tmp_path / "stop-request.json").write_text("{}")
    with pytest.raises(RunStopped, match="Operator"):
        UsageLedger(tmp_path / "usage.json", Config()).reserve("analysis", None)


def test_duplicate_acceptance_does_not_pass(tmp_path):
    manager = make_manager(tmp_path, {})
    task = BacklogTask("T", "Task", acceptance_criteria=["one", "two"])
    obj = {"verdict": "PASS", "acceptance": [
        {"criterion_id": "AC-1", "status": "PASS", "evidence": "test"},
        {"criterion_id": "AC-1", "status": "PASS", "evidence": "test"},
    ]}
    manager._normalize_task_qa(task, obj)
    assert obj["verdict"] == "UNVERIFIED"


def test_acceptance_ids_cover_distinct_criteria(tmp_path):
    manager = make_manager(tmp_path, {})
    task = BacklogTask("T", "Task", acceptance_criteria=["one", "two"])
    obj = {"verdict": "PASS", "acceptance": [
        {"criterion_id": f"AC-{i}", "status": "PASS", "evidence": "test"} for i in [2, 1]
    ]}
    manager._normalize_task_qa(task, obj)
    assert obj["verdict"] == "PASS"


def test_resume_does_not_mutate_state_before_lock(tmp_path):
    manager = make_manager(tmp_path, {"T": BacklogTask("T", "Task", status=TaskStatus.PLANNING)})
    manager._persist()
    before = manager.paths.state_file.read_bytes()
    manager._acquire_run_lock()
    try:
        second = Orchestrator.resume(manager.repo, manager.config, "recovery")
        with pytest.raises(RuntimeError, match="already active"):
            second.run()
        assert manager.paths.state_file.read_bytes() == before
    finally:
        manager._release_run_lock()


def test_repair_recovery_keeps_intent(tmp_path):
    task = BacklogTask("T", "Task", status=TaskStatus.IMPLEMENTING,
                       metadata={"resume_mode": "repair"})
    manager = make_manager(tmp_path, {"T": task})
    manager._recover_interrupted_tasks()
    assert task.metadata["resume_mode"] == "repair"


def test_restart_limit_applies_before_diagnosis(tmp_path):
    task = BacklogTask("T", "Task", generation=2)
    manager = make_manager(tmp_path, {"T": task})
    with pytest.raises(RunStopped, match="generation limit"):
        manager._clean_restart(task, tmp_path, "plan", "evidence")
    assert not manager.usage.path.exists()


def test_checks_capture_failure_and_stop_early(tmp_path):
    commands = [f'"{sys.executable}" -c "print(123); raise SystemExit(7)"', 'should-not-run']
    results = run_checks(commands, tmp_path, timeout=10, limit=100)
    assert len(results) == 1
    assert results[0]["exit_code"] == 7
    assert "123" in results[0]["output"]


def test_checks_bound_output_and_timeout(tmp_path):
    results = run_checks([f'"{sys.executable}" -c "print(\'x\'*1000)"'], tmp_path, timeout=10, limit=32)
    assert results[0]["output_truncated"]
    assert len(results[0]["output"]) <= 32
    results = run_checks([f'"{sys.executable}" -c "import time; time.sleep(30)"'], tmp_path, timeout=1, limit=32)
    assert results[0]["timed_out"]


def test_preflight_failure_skips_model_qa(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, Config(verification_commands=[f'"{sys.executable}" -c "raise SystemExit(1)"']))
    task = manager.state.tasks["TASK-001"]
    result = manager._run_qa(task, "plan", manager.state.base_commit)
    assert result["verdict"] == "FAIL"
    assert result["checkpoint_commit"] == manager.state.base_commit
    assert not manager.usage.path.exists()


def test_backlog_only_change_skips_model_review(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, Config())
    task = manager.state.tasks["TASK-001"]
    task.plan_base_commit = manager.state.base_commit
    assert manager._ensure_plan_current(task)
    assert not manager.usage.path.exists()


def test_optional_final_review_and_reports(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, Config(final_code_review=True, qa_passes_per_code_review=10))
    manager.claude = FakeClaude()
    manager.run()
    assert manager.state.qa_passes_since_review == 0
    report = run_report(manager.paths.run_dir)
    assert report["completed"] == 3
    report["tasks"][0]["title"] = "<script>alert(1)</script>"
    output = tmp_path / "report.html"
    write_html(report, output)
    assert "<script>" not in output.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in output.read_text(encoding="utf-8")


def test_cli_stop_report_retry_and_cleanup_lock(tmp_path):
    manager = make_manager(tmp_path, {"T": BacklogTask("T", "Task", status=TaskStatus.UNPLANNED,
        plan_path="plan.md", blocked_reason="rework limit", metadata={"blocked_kind": "plan_rework_limit"})})
    manager._persist()
    prefix = ["--repo", str(manager.repo)]
    assert main(prefix + ["stop", "--run-id", "recovery"]) == 0
    assert (manager.paths.run_dir / "stop-request.json").exists()
    output = tmp_path / "report.html"
    assert main(prefix + ["report", "--run-id", "recovery", "--html", str(output)]) == 0
    assert output.exists()
    manager._acquire_run_lock()
    try:
        assert main(prefix + ["cleanup", "--run-id", "recovery"]) == 2
        assert main(prefix + ["retry", "--run-id", "recovery", "--task", "T"]) == 2
    finally:
        manager._release_run_lock()
    assert main(prefix + ["retry", "--run-id", "recovery", "--task", "T"]) == 0
    saved = json.loads(manager.paths.state_file.read_text(encoding="utf-8"))
    assert saved["tasks"]["T"]["status"] == "PLAN_REVIEW"


def test_task_call_budget_is_independent(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.json", Config(max_task_agent_calls=1))
    ledger.reserve("implementer", "A")
    with pytest.raises(RunStopped, match="Task A"):
        ledger.reserve("read_only", "A")
    ledger.reserve("implementer", "B")


def test_budget_stop_is_persisted_and_resume_rechecks_it(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, Config(max_agent_calls=1))
    manager.claude = FakeClaude()
    manager.run()
    assert manager.state.paused
    assert "budget" in manager.state.stop_reason
    reloaded = Orchestrator.resume(repo, manager.config, manager.state.run_id)
    reloaded.claude = FakeClaude()
    reloaded.run()
    assert reloaded.state.paused
    assert len(reloaded.usage.read()["calls"]) == 1


def test_model_scheduler_remains_available(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, Config(scheduler="model"))
    manager.claude = FakeClaude()
    manager.run()
    assert manager.state.stop_reason == "all tasks complete"


def test_finished_parallel_plans_survive_budget_stop(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, Config(max_agent_calls=3))
    for task in manager.state.tasks.values():
        task.dependencies = []
    manager.claude = FakeClaude()
    manager.run()
    assert manager.state.paused
    assert all(t.status == TaskStatus.PLAN_REVIEW for t in manager.state.tasks.values())
    assert all((repo / t.plan_path).exists() for t in manager.state.tasks.values())


def test_claude_receives_estimated_call_cap(monkeypatch, tmp_path):
    from opus_manager.claude import ClaudeClient
    captured = {}
    class Result:
        stdout = '{"result":"OK","total_cost_usd":0.01}'
        stderr = ""
        returncode = 0
    def run(command, **kwargs):
        captured["command"] = command
        return Result()
    monkeypatch.setattr("opus_manager.claude.subprocess.run", run)
    ClaudeClient(Config(), tmp_path).run("test", cwd=tmp_path, role="analysis", max_turns=1, budget_usd=1.5)
    command = captured["command"]
    assert command[command.index("--max-budget-usd") + 1] == "1.5"


def test_benchmark_grader_rejects_bad_code_and_accepts_correct_code(tmp_path):
    import runpy
    benchmark = runpy.run_path(str(Path(__file__).parents[1] / "evaluations" / "run.py"))
    source = tmp_path / "helpers.py"
    source.write_text("def clamp(*args): return None\ndef slug(*args): return None\ndef mean(*args): return None\n")
    assert not any(r["pass"] for r in benchmark["grade"](tmp_path).values())
    source.write_text("import re\ndef clamp(v,l,h): return min(h,max(l,v))\ndef slug(t): return re.sub('[^a-z0-9]+', '-', t.lower()).strip('-')\ndef mean(v): return sum(v)/len(v) if v else None\n")
    assert all(r["pass"] for r in benchmark["grade"](tmp_path).values())
