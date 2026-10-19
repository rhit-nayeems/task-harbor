import pytest

from opus_manager.claude import ClaudeClient, ClaudeError, extract_json
from opus_manager.config import Config


def test_extract_json_plain_and_fenced():
    assert extract_json('{"verdict":"PASS"}')["verdict"] == "PASS"
    assert extract_json('```json\n{"verdict":"FAIL"}\n```')["verdict"] == "FAIL"
    assert extract_json('note before {"x":1} after')["x"] == 1


def test_extract_json_rejects_missing_object():
    with pytest.raises(ClaudeError):
        extract_json("nothing structured here")


def test_config_validates_claude_effort():
    assert Config(effort="XHIGH").effort == "xhigh"
    with pytest.raises(ValueError, match="Invalid Claude effort"):
        Config(effort="unlimited")


def test_claude_client_passes_configured_effort(monkeypatch, tmp_path):
    captured = {}

    class Process:
        stdout = '{"result":"OK","session_id":"s1"}'
        stderr = ""
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return Process()

    monkeypatch.setattr("opus_manager.claude.subprocess.run", fake_run)
    client = ClaudeClient(Config(effort="xhigh"), tmp_path / "hooks")
    client.run("test", cwd=tmp_path, role="analysis", max_turns=1)

    index = captured["cmd"].index("--effort")
    assert captured["cmd"][index + 1] == "xhigh"


def test_loading_old_config_persists_new_default_fields(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"model":"opus","local_extension":"kept"}\n', encoding="utf-8")

    cfg = Config.load(path)
    migrated = __import__("json").loads(path.read_text(encoding="utf-8"))

    assert cfg.effort == "medium"
    assert migrated["effort"] == "medium"
    assert migrated["local_extension"] == "kept"
