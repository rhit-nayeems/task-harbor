import json
import sys
from pathlib import Path

import pytest

from opus_manager.backlog import render_backlog
from opus_manager.cli import main
from opus_manager.comparison import compare
from opus_manager.config import Config
from opus_manager.contracts import validate_contract
from opus_manager.evidence import change_evidence, review_chunks
from opus_manager.gitops import git, head
from opus_manager.models import BacklogTask, TaskStatus
from opus_manager.orchestrator import Orchestrator
from opus_manager.preflight import baseline
from opus_manager.reporting import run_report, review_text, write_html
from opus_manager.state import atomic_write_json
from test_orchestrator_integration import init_repo, FakeClaude, EscalationClaude


def command(code):
    return f'"{sys.executable}" -c "{code}"'


def project(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    render_backlog(repo / "BACKLOG.md", {"TASK-001": BacklogTask("TASK-001", "One", acceptance_criteria=["works"])})
    git(repo, "add", ".")
    git(repo, "commit", "-m", "one task")
    return repo


def test_preflight_failure_and_missing_environment_do_not_call_agents(tmp_path):
    repo = project(tmp_path)
    result = baseline(repo, Config(verification_commands=[command("raise SystemExit(1)")]), head(repo))
    assert result["status"] == "FAIL"
    cfg = Config(required_env=["HARBOR_TEST_MISSING_VARIABLE_628"], verification_commands=[command("print('ok')")])
    manager = Orchestrator.start(repo, cfg)
    fake = FakeClaude()
    manager.agent = fake
    manager.run()
    assert manager.state.paused
    assert fake.n == 0
    assert "environment blocked" in manager.state.stop_reason


def test_required_checks_stop_before_spending(tmp_path):
    manager = Orchestrator.start(project(tmp_path), Config(require_verification=True))
    manager.agent = FakeClaude()
    manager.run()
    assert manager.agent.n == 0
    assert manager.state.paused


def test_contract_question_answer_and_resume(tmp_path, capsys):
    repo = project(tmp_path)
    atomic_write_json(repo / ".manager/contracts.json", {"TASK-001": {"questions": {"Q-1": "Which format?"}}})
    manager = Orchestrator.start(repo, Config())
    manager.agent = FakeClaude()
    manager.run()
    assert manager.agent.n == 0
    prefix = ["--repo", str(repo)]
    assert main(prefix + ["questions", "--run-id", manager.state.run_id]) == 0
    assert "Which format?" in capsys.readouterr().out
    assert main(prefix + ["answer", "--run-id", manager.state.run_id, "--task", "TASK-001", "--question", "Q-1", "--text", "UTF-8"]) == 0
    resumed = Orchestrator.resume(repo, Config(), manager.state.run_id)
    resumed.agent = FakeClaude()
    resumed.run()
    assert resumed.state.tasks["TASK-001"].status == TaskStatus.COMPLETE
    assert resumed.state.tasks["TASK-001"].metadata["contract"]["answers"]["Q-1"] == "UTF-8"


def test_adaptive_agreement_evidence_and_reproduction(tmp_path):
    repo = project(tmp_path)
    check = command("from pathlib import Path; assert Path('TASK-001.txt').exists()")
    atomic_write_json(repo / ".manager/contracts.json", {"TASK-001": {"risk": "low", "allowed_paths": ["TASK-001.txt"],
                      "acceptance_checks": {"AC-1": [check]}, "reproduction_commands": [check]}})
    cfg = Config(workflow="adaptive", max_agent_calls=3, qa_passes_per_code_review=99)
    manager = Orchestrator.start(repo, cfg)
    manager.agent = FakeClaude()
    manager.run()
    assert manager.state.tasks["TASK-001"].status == TaskStatus.COMPLETE
    assert manager.agent.n == 3  # implementation, independent QA, focused code review
    report = run_report(manager.paths.run_dir)
    evidence = report["tasks"][0]["evidence"]
    assert evidence["reproduction"]["before"]["status"] == "FAIL"
    assert evidence["reproduction"]["after"][0]["exit_code"] == 0
    assert evidence["acceptance_checks"]["AC-1"][0]["exit_code"] == 0
    assert evidence["focused_review"]["coverage"]
    assert "TASK-001.txt" in review_text(report)
    output = tmp_path / "review.html"
    write_html(report, output)
    assert "Evidence and diffs" in output.read_text(encoding="utf-8")


def test_review_chunk_coverage_is_complete_and_cached(tmp_path):
    repo = project(tmp_path)
    manager = Orchestrator.start(repo, Config(evidence_max_chars=80))
    worktree = Path(manager.state.integration_worktree)
    base = head(worktree)
    (worktree / "long.txt").write_text("new line\n" * 60)
    git(worktree, "add", "long.txt")
    git(worktree, "commit", "-m", "long change")
    tip = head(worktree)
    evidence = change_evidence(repo, base, tip, manager.config)
    chunks = list(review_chunks(evidence, 80))
    assert "".join(c["diff"] for c in chunks) == evidence["files"][0]["diff"]
    manager.agent = FakeClaude()
    result = manager._review_changes(worktree, base, tip, [])
    assert len(result["coverage"]) == len(chunks)
    count = manager.agent.n
    assert manager._review_changes(worktree, base, tip, []) == result
    assert manager.agent.n == count


def test_review_fixes_cannot_skip_deterministic_checks(tmp_path):
    repo = project(tmp_path)
    manager = Orchestrator.start(repo, Config(verification_commands=[command("raise SystemExit(1)")], max_code_review_fix_attempts=0))

    class Fixer(FakeClaude):
        def run(self, prompt, **kwargs):
            assert "implementer assigned to resolve" in prompt
            (Path(kwargs["cwd"]) / "fixed.txt").write_text("fixed")
            return self._r("fixed")

    manager.agent = Fixer()
    assert not manager._fix_code_review({"verdict": "CHANGES_REQUIRED", "findings": []})
    assert manager.agent.n == 1  # no model QA call after a failed deterministic check
    artifact = json.loads((manager.paths.reviews_dir / "review_fix_qa_0.json").read_text())
    assert artifact["harness_checks"][0]["exit_code"] == 1
    assert artifact["verdict"] == "UNVERIFIED"


def test_repeated_unchanged_failures_stop(tmp_path):
    manager = Orchestrator.start(project(tmp_path), Config(repeated_failure_limit=2))
    manager.agent = EscalationClaude()
    manager.run()
    task = manager.state.tasks["TASK-001"]
    assert manager.state.paused
    assert task.metadata["blocked_kind"] == "no_progress"
    assert task.generation == 0


@pytest.mark.parametrize("contract", [{"risk": "maybe"}, {"questions": []}, {"answers": {"Q": "answer"}},
    {"acceptance_checks": {"AC-2": ["test"]}}, {"surprise_command": "test"}])
def test_invalid_contracts(contract):
    with pytest.raises(ValueError):
        validate_contract(contract, 1)


def test_comparison_preparation_has_no_agent_or_grader_calls(tmp_path, monkeypatch):
    repo = project(tmp_path)
    manifest = tmp_path / "manifest.json"
    atomic_write_json(manifest, {"repo": str(repo), "commit": head(repo), "tasks": [{"id": "T", "title": "Task", "acceptance_criteria": ["works"], "grader_commands": ["never execute this"]}]})
    monkeypatch.setattr("opus_manager.comparison.create_client", lambda *a: pytest.fail("provider invoked"))
    monkeypatch.setattr("opus_manager.comparison.run_checks", lambda *a, **k: pytest.fail("grader invoked"))
    result = compare(manifest, tmp_path / "comparison", repetitions=2)
    assert result["model_calls"] == 0
    assert result["trials"] == 4
    assert not list((tmp_path / "comparison").glob("*/repo"))


def test_comparison_runs_both_arms_with_fake_provider(tmp_path, monkeypatch):
    repo = project(tmp_path)
    check = command("from pathlib import Path; assert Path('TASK-001.txt').exists()")
    manifest = tmp_path / "manifest.json"
    atomic_write_json(manifest, {"repo": str(repo), "commit": head(repo), "config": {"claude_bin": "harbor-test-no-cli"},
        "tasks": [{"id": "TASK-001", "title": "One", "acceptance_criteria": ["works"], "grader_commands": [check]}]})

    class Agent(FakeClaude):
        def run(self, prompt, **kwargs):
            if prompt.startswith("Implement this task"):
                (Path(kwargs["cwd"]) / "TASK-001.txt").write_text("works")
                return self._r("implemented")
            return super().run(prompt, **kwargs)

    monkeypatch.setattr("opus_manager.comparison.create_client", lambda *a: Agent())
    monkeypatch.setattr("opus_manager.orchestrator.create_client", lambda *a: Agent())
    summary = compare(manifest, tmp_path / "comparison", live=True)
    assert summary["direct"]["independently_passing"] == 1
    assert summary["harbor"]["independently_passing"] == 1
    rows = json.loads((tmp_path / "comparison/results.json").read_text())
    assert all(r["human_active_minutes"] is None for r in rows)
    assert all("usage" in r for r in rows)


def test_artifacts_retained_and_tracked_changes_rejected(tmp_path):
    from opus_manager.preflight import execute_checks, collect_artifacts
    repo = project(tmp_path)
    cfg = Config(verification_commands=[command("from pathlib import Path; Path('result.txt').write_text('check output')")], verification_artifacts=["result.txt"])
    assert execute_checks(cfg, repo)["status"] == "PASS"
    records = collect_artifacts(cfg, repo, tmp_path / "retained")
    assert records[0]["status"] == "retained"
    assert Path(records[0]["path"]).read_text() == "check output"
    git(repo, "add", "result.txt")
    git(repo, "commit", "-m", "track output")
    (repo / "result.txt").write_text("changed")
    cfg.verification_commands = []
    assert execute_checks(cfg, repo)["status"] == "ENVIRONMENT_BLOCKED"


def test_feedback_is_reported_separately(tmp_path):
    repo = project(tmp_path)
    manager = Orchestrator.start(repo, Config())
    assert main(["--repo", str(repo), "feedback", "--run-id", manager.state.run_id,
                 "--task", "TASK-001", "--outcome", "needs_changes", "--minutes", "4.5"]) == 0
    report = run_report(manager.paths.run_dir)
    assert report["active_review_minutes"] == 4.5
    assert report["feedback"][0]["outcome"] == "needs_changes"
    assert "needs_changes" in review_text(report)
    assert report["tasks"][0]["status"] == "UNPLANNED"


def test_reviewer_questions_survive_restart_without_overwriting_answers(tmp_path):
    repo = project(tmp_path)
    atomic_write_json(repo / ".manager/contracts.json", {"TASK-001": {
        "questions": {"Q-2": "Existing question"}, "answers": {"Q-2": "Existing answer"}}})
    class AskingAgent(FakeClaude):
        def run(self, prompt, **kwargs):
            if "IT Manager reviewing a planner" in prompt:
                return self._r(json.dumps({"verdict": "NEEDS_CLARIFICATION", "questions": ["Which format?"]}))
            return super().run(prompt, **kwargs)
    manager = Orchestrator.start(repo, Config())
    manager.agent = AskingAgent()
    manager.run()
    resumed = Orchestrator.resume(repo, Config(), manager.state.run_id)
    contract = resumed.state.tasks["TASK-001"].metadata["contract"]
    assert contract["questions"] == {"Q-2": "Existing question", "Q-1": "Which format?"}
    assert contract["answers"]["Q-2"] == "Existing answer"
    assert main(["--repo", str(repo), "answer", "--run-id", manager.state.run_id,
                 "--task", "TASK-001", "--question", "Q-1", "--text", "UTF-8"]) == 0
    resumed = Orchestrator.resume(repo, Config(), manager.state.run_id)
    resumed.agent = FakeClaude()
    resumed.run()
    assert resumed.state.tasks["TASK-001"].status == TaskStatus.COMPLETE


def test_rename_review_covers_old_and_new_paths(tmp_path):
    repo = project(tmp_path)
    (repo / "old.txt").write_text("preserve content")
    git(repo, "add", "old.txt")
    git(repo, "commit", "-m", "original file")
    base = head(repo)
    git(repo, "mv", "old.txt", "new.txt")
    git(repo, "commit", "-m", "rename")
    evidence = change_evidence(repo, base, head(repo), Config())
    assert {f["path"] for f in evidence["files"]} == {"old.txt", "new.txt"}
    assert all(f["diff"] for f in evidence["files"])
