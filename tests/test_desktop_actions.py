from types import SimpleNamespace

from opus_manager.desktop_actions import launch_run


def test_launch_uses_arguments_no_shell_and_keeps_output(tmp_path, monkeypatch):
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        kwargs["stdout"].write(b"launch output")
        return SimpleNamespace(pid=123)

    monkeypatch.setattr("opus_manager.desktop_actions.subprocess.Popen", popen)
    repo = tmp_path / "project with spaces"
    repo.mkdir()
    process, log = launch_run(repo, repo / ".manager/runs", "saved-001")
    assert process.pid == 123
    assert log.read_text() == "launch output"
    command, options = calls[0]
    assert command[-3:] == ["resume", "--run-id", "saved-001"]
    assert str(repo) in command
    assert not options.get("shell", False)
