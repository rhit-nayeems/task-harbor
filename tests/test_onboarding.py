import json
from types import SimpleNamespace

from opus_manager.cli import main
from opus_manager.gitops import git
from opus_manager.reporting import review_summary, run_report
from test_orchestrator_integration import init_repo


def test_demo_runs_real_checks_and_preserves_existing_destination(tmp_path, monkeypatch, capsys):
    import opus_manager.providers
    monkeypatch.setattr(opus_manager.providers, "create_client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Provider called")))
    repo = tmp_path / "sample with spaces"
    assert main(["demo", "--output", str(repo)]) == 0
    report = run_report(repo / ".manager/runs/demo-001")
    evidence = report["tasks"][0]["evidence"]
    assert evidence["reproduction"]["before"]["checks"][0]["exit_code"] != 0
    assert evidence["harness_checks"][0]["exit_code"] == 0
    assert "Ran 2 tests" in evidence["harness_checks"][0]["output"]
    assert evidence["changes"]["files"][0]["path"] == "search.py"
    assert "pending for this checkpoint" in (repo / "review.html").read_text(encoding="utf-8")
    assert main(["--repo", str(repo), "review", "--run-id", "demo-001"]) == 0
    assert main(["--repo", str(repo), "feedback", "--run-id", "demo-001", "--task", "BUG-001",
                 "--outcome", "accepted", "--minutes", "2", "--supervision-minutes", "3", "--repair-minutes", "0"]) == 0
    feedback = run_report(repo / ".manager/runs/demo-001")["feedback"]
    assert feedback[0]["active_engineer_minutes"] == 5
    assert main(["--repo", str(repo), "feedback", "--run-id", "demo-001", "--task", "BUG-001",
                 "--outcome", "accepted", "--minutes", "2", "--repair-minutes", "nan"]) == 2
    assert len(run_report(repo / ".manager/runs/demo-001")["feedback"]) == 1
    assert "accepted for this checkpoint" in "\n".join(review_summary(run_report(repo / ".manager/runs/demo-001")["tasks"][0],
                                                                   run_report(repo / ".manager/runs/demo-001")["feedback"]))
    before = git(repo, "rev-parse", "HEAD").stdout
    assert main(["demo", "--output", str(repo)]) == 2
    assert git(repo, "rev-parse", "HEAD").stdout == before


def test_setup_validates_before_writing_and_keeps_custom_settings(tmp_path, monkeypatch):
    repo = tmp_path / "project"
    init_repo(repo)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    prefix = ["--repo", str(repo), "setup", "--provider", "codex", "--model", "gpt-test", "--check", "python -m unittest"]
    assert main(prefix + ["--max-agent-calls", "0"]) == 2
    assert not (repo / ".manager/config.json").exists()
    assert main(prefix) == 0
    assert ".manager" not in git(repo, "status", "--porcelain").stdout
    path = repo / ".manager/config.json"
    cfg = json.loads(path.read_text())
    assert cfg["require_verification"] and cfg["max_agent_calls"] == 20
    cfg["local_custom_setting"] = "keep"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    backlog = repo / "BACKLOG.md"
    backlog.write_text("Existing tasks", encoding="utf-8")
    assert main(prefix + ["--max-agent-calls", "12"]) == 0
    assert json.loads(path.read_text())["local_custom_setting"] == "keep"
    assert backlog.read_text() == "Existing tasks"


def test_summary_does_not_treat_missing_checks_or_old_feedback_as_verified():
    task = {"id": "T-1", "checkpoint": "new", "evidence": {}, "acceptance_criteria": ["works"]}
    text = "\n".join(review_summary(task, [{"task": "T-1", "checkpoint": "old", "outcome": "accepted"}]))
    assert "NOT VERIFIED" in text and "no executed checks" in text
    assert "missing or does not match" in text and "pending for this checkpoint" in text


def test_interactive_setup_records_choices_without_executing_checks(tmp_path, monkeypatch):
    repo = tmp_path / "project"
    init_repo(repo)
    (repo / "BACKLOG.md").unlink()
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    answers = iter(["claude", "opus", "command-that-must-not-be-executed", "8", "BUG-001", "Handle empty input", "Empty input returns an empty list", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert main(["--repo", str(repo), "setup"]) == 0
    cfg = json.loads((repo / ".manager/config.json").read_text())
    assert cfg["max_agent_calls"] == 8
    assert cfg["verification_commands"] == ["command-that-must-not-be-executed"]
    from opus_manager.backlog import parse_backlog
    tasks = parse_backlog(repo / "BACKLOG.md")
    assert tasks["BUG-001"].acceptance_criteria == ["Empty input returns an empty list"]


def test_add_task_keeps_existing_text_and_refuses_duplicate(tmp_path, monkeypatch):
    repo = tmp_path / "project"
    init_repo(repo)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    prefix = ["--repo", str(repo), "add-task", "--task-id", "BUG-001", "--title", "Handle empty input",
              "--accept", "Empty input returns an empty list"]
    assert main(prefix) == 0
    path = repo / "BACKLOG.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n<!-- Keep this note -->\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert main(prefix) == 2
    assert path.read_text(encoding="utf-8") == before
    assert main(["--repo", str(repo), "add-task", "--task-id", "BUG-002", "--title", "Keep normal behavior", "--accept", "Normal input still works"]) == 0
    assert path.read_text(encoding="utf-8").startswith(before.rstrip())
