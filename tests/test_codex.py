import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from opus_manager.agent import AgentError
from opus_manager.codex import CodexClient, executable_command, parse_events
from opus_manager.config import Config
from opus_manager.models import ManagerState
from opus_manager.orchestrator import Orchestrator, ManagerError
from opus_manager.providers import create_client
from test_orchestrator_integration import init_repo, FakeClaude, EscalationClaude


def events(text="OK", session=None):
    return "\n".join(json.dumps(e) for e in [
        {"type": "thread.started", "thread_id": session or str(uuid4())},
        {"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": "not the answer"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10}},
    ])


def config(**kwargs):
    return Config(provider="codex", model="gpt-test", codex_bin="codex-test", **kwargs)


def test_parse_events_and_usage():
    result = parse_events(events(), 0)
    assert result.text == "OK"
    assert result.session_id
    assert result.raw["usage"]["cached_input_tokens"] == 80
    assert "total_cost_usd" not in result.raw


@pytest.mark.parametrize("payload,code", [
    ("not json", 0), ("[]", 0), ('{"type":"turn.completed"}', 0),
    (events(), 1), (events() + '\n{"type":"turn.failed","error":{"message":"failed"}}', 0),
    (events() + '\n{"type":"error","message":"failed"}', 0),
])
def test_malformed_or_failed_turn_never_passes(payload, code):
    with pytest.raises(AgentError):
        parse_events(payload, code)


@pytest.mark.parametrize("role,sandbox", [("analysis", "read-only"), ("read_only", "read-only"), ("implementer", "workspace-write")])
def test_roles_use_explicit_sandbox_and_stdin(monkeypatch, tmp_path, role, sandbox):
    captured = {}
    def fake_run(cmd, **kwargs):
        captured.update(cmd=cmd, **kwargs)
        return SimpleNamespace(stdout=events(), stderr="", returncode=0)
    monkeypatch.setattr("opus_manager.codex.subprocess.run", fake_run)
    result = CodexClient(config(), tmp_path).run("sensitive prompt", cwd=tmp_path, role=role, max_turns=4)
    assert result.text == "OK"
    assert f'sandbox_mode="{sandbox}"' in captured["cmd"]
    assert 'approval_policy="never"' in captured["cmd"]
    assert 'model_provider="openai"' in captured["cmd"]
    assert "sensitive prompt" not in captured["cmd"]
    assert "sensitive prompt" in captured["input"]
    assert captured["timeout"] == 3600
    assert captured["cmd"][-1] == "-"
    assert not any("bypass" in a for a in captured["cmd"])


def test_resume_targets_exact_session(monkeypatch, tmp_path):
    session = str(uuid4())
    captured = []
    def run(cmd, **kwargs):
        captured.extend(cmd)
        return SimpleNamespace(stdout=events(session=session), stderr="", returncode=0)
    monkeypatch.setattr("opus_manager.codex.subprocess.run", run)
    result = CodexClient(config(), tmp_path).run("repair", cwd=tmp_path, role="implementer", max_turns=4, resume_session=session)
    assert captured[1:3] == ["exec", "resume"]
    assert captured[-2:] == [session, "-"]
    assert result.session_id == session
    with pytest.raises(AgentError, match="different thread"):
        parse_events(events(), 0, resume_session=session)


@pytest.mark.parametrize("kwargs", [{"max_run_cost_usd": 5}, {"max_call_cost_usd": 1}, {"effort": "invalid"}])
def test_unsupported_controls_rejected(kwargs):
    with pytest.raises(ValueError):
        config(**kwargs)


def test_codex_requires_explicit_gpt_model():
    with pytest.raises(ValueError, match="GPT model"):
        Config(provider="codex")


def test_factory_and_legacy_state(tmp_path):
    assert isinstance(create_client(config(), tmp_path), CodexClient)
    state = ManagerState.from_dict(dict(run_id="old", repo="repo", integration_branch="i", integration_worktree="w", base_branch="main", base_commit="sha"))
    assert state.provider == "claude"


def test_no_cross_provider_session_resume(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    original = Orchestrator.start(repo, Config())
    before = original.paths.state_file.read_bytes()
    with pytest.raises(ManagerError, match="Cannot change provider"):
        Orchestrator.resume(repo, config(), original.state.run_id)
    assert original.paths.state_file.read_bytes() == before


def test_missing_binary_and_timeout(monkeypatch, tmp_path):
    def missing(*args, **kwargs):
        raise FileNotFoundError()
    monkeypatch.setattr("opus_manager.codex.subprocess.run", missing)
    client = CodexClient(config(), tmp_path)
    with pytest.raises(AgentError, match="not found"):
        client.probe(tmp_path)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("codex", 1)
    monkeypatch.setattr("opus_manager.codex.subprocess.run", timeout)
    with pytest.raises(AgentError, match="timed out"):
        client.probe(tmp_path)


def test_windows_npm_launcher_avoids_shell(monkeypatch, tmp_path):
    wrapper = tmp_path / "codex.cmd"
    entry = tmp_path / "node_modules/@openai/codex/bin/codex.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// launcher")
    monkeypatch.setattr("opus_manager.codex.shutil.which", lambda name: "node.exe" if name == "node" else str(wrapper))
    assert executable_command("codex") == ["node.exe", str(entry)]


def test_full_gpt_workflow_through_adapter(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, config(max_agent_calls=30))
    actual_run = subprocess.run
    fake = FakeClaude()
    def run(cmd, **kwargs):
        if cmd[0] != "codex-test":
            return actual_run(cmd, **kwargs)
        response = fake.run(kwargs["input"], cwd=Path(kwargs["cwd"]), role="unused", max_turns=1)
        return SimpleNamespace(stdout=events(response.text), stderr="", returncode=0)
    monkeypatch.setattr("opus_manager.codex.subprocess.run", run)
    manager.run()
    assert manager.state.stop_reason == "all tasks complete"
    assert manager.state.provider == "codex"
    assert all(c["provider"] == "codex" for c in manager.usage.read()["calls"])
    assert all(c["usage"]["input_tokens"] == 100 for c in manager.usage.read()["calls"])


def test_gpt_repairs_resume_then_restart_fresh(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    manager = Orchestrator.start(repo, config(qa_passes_per_code_review=99))
    manager.state.tasks = {"TASK-001": manager.state.tasks["TASK-001"]}
    actual_run = subprocess.run
    fake = EscalationClaude()
    sessions = {}
    def run(cmd, **kwargs):
        if cmd[0] != "codex-test":
            return actual_run(cmd, **kwargs)
        resumed = next((name for name, sid in sessions.items() if sid == cmd[-2]), None) if "resume" in cmd else None
        response = fake.run(kwargs["input"], cwd=Path(kwargs["cwd"]), role="unused", max_turns=1, resume_session=resumed)
        sid = sessions.setdefault(response.session_id, str(uuid4()))
        return SimpleNamespace(stdout=events(response.text, sid), stderr="", returncode=0)
    monkeypatch.setattr("opus_manager.codex.subprocess.run", run)
    manager.run()
    assert fake.resume_ids == ["poison-session", "poison-session"]
    task = manager.state.tasks["TASK-001"]
    assert task.implementer_session_id == sessions["fresh-session"]
    assert task.generation == 1
    assert task.status.value == "COMPLETE"
