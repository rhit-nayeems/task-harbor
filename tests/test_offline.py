import json

import pytest

from opus_manager.cli import main
from opus_manager.config import Config
from opus_manager.gitops import git
from opus_manager.models import BacklogTask, ManagerState, TaskStatus
from opus_manager.offline import readiness, saved_runs
from opus_manager.state import atomic_write_json
from test_orchestrator_integration import init_repo


@pytest.fixture(autouse=True)
def no_agent(monkeypatch):
    monkeypatch.setattr("opus_manager.providers.create_client",
                        lambda *a, **kw: pytest.fail("Offline command created an agent"))


def test_readiness_does_not_create_config_or_execute_recipe(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo(repo)
    monkeypatch.setattr("opus_manager.offline.shutil.which", lambda name: str(repo / name))
    before = git(repo, "status", "--porcelain").stdout
    result = readiness(repo)
    assert result["model_calls"] == 0
    assert not (repo / ".manager").exists()
    assert git(repo, "status", "--porcelain").stdout == before
    assert any(c["name"] == "Verification" and c["status"] == "warning" for c in result["checks"])


def test_readiness_hides_environment_and_does_not_run_commands(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo(repo)
    monkeypatch.setenv("HARBOR_OFFLINE_TEST", "do-not-print-this-value")
    (repo / ".manager").mkdir()
    cfg = Config(required_env=["HARBOR_OFFLINE_TEST", "HARBOR_ABSENT_987"],
                 verification_commands=["never execute this"], setup_commands=["never execute this either"])
    cfg.save(repo / ".manager/config.json")
    before = (repo / ".manager/config.json").read_bytes()
    result = readiness(repo)
    assert not result["ready"]
    assert "do-not-print-this-value" not in json.dumps(result)
    assert before == (repo / ".manager/config.json").read_bytes()


def test_check_json_handles_invalid_config_and_dependency_errors(tmp_path, capsys):
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / ".manager").mkdir()
    (repo / ".manager/config.json").write_text("[]")
    assert main(["--repo", str(repo), "check", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["checks"][0]["name"] == "Configuration"
    (repo / ".manager/config.json").write_text("{}")
    (repo / "BACKLOG.md").write_text("## T — Test\n- **Dependencies:** MISSING\n", encoding="utf-8")
    assert main(["--repo", str(repo), "check", "--json"]) == 2
    assert "unknown dependency" in capsys.readouterr().out


def test_runs_filter_and_corruption_are_independent(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = repo / ".manager/runs"
    for run_id, complete, paused in [("one", True, False), ("two", False, True), ("three", False, False)]:
        state = ManagerState(run_id, str(repo), "integration", "worktree", "main", "abc",
                             tasks={"T": BacklogTask("T", "Task", status=TaskStatus.COMPLETE if complete else TaskStatus.READY)},
                             paused=paused)
        atomic_write_json(root / run_id / "state.json", state.to_dict())
    (root / "broken").mkdir()
    (root / "broken/state.json").write_text("{broken")
    result = saved_runs(repo, "paused")
    assert [r["id"] for r in result["runs"]] == ["two"]
    assert [e["id"] for e in result["errors"]] == ["broken"]
    assert main(["--repo", str(repo), "runs", "--json"]) == 2
    data = json.loads(capsys.readouterr().out)
    assert {r["status"] for r in data["runs"]} == {"complete", "paused", "unfinished"}


def test_empty_runs_is_read_only(tmp_path, capsys):
    assert main(["--repo", str(tmp_path), "runs"]) == 0
    assert "No saved runs" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_ready_project_and_dirty_worktree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo(repo)
    monkeypatch.setattr("opus_manager.offline.shutil.which", lambda name: str(repo / name))
    (repo / ".manager").mkdir()
    Config(require_verification=True, verification_commands=["never execute"],
           max_agent_calls=10).save(repo / ".manager/config.json")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "configuration")
    assert readiness(repo)["ready"]
    (repo / "README.md").write_text("dirty")
    result = readiness(repo)
    assert not result["ready"]
    assert any(c["name"] == "Working tree" and c["status"] == "error" for c in result["checks"])
    (repo / "BACKLOG.md").write_text("## T - Missing criteria\n", encoding="utf-8")
    result = readiness(repo)
    assert any(c["name"] == "Acceptance: T" and c["status"] == "error" for c in result["checks"])
