import builtins

from opus_manager.cli import main


def test_guide_does_not_create_project_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["guide"]) == 0
    assert "TROUBLESHOOTING" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_default_command_opens_dashboard(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    launched = []

    class Dashboard:
        def __init__(self, repo, run_id):
            launched.append((repo, run_id))

        def run(self):
            launched.append("started")

    monkeypatch.setitem(sys.modules, "textual", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "opus_manager.tui", SimpleNamespace(HarborApp=Dashboard))
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
    assert launched == [(tmp_path, None), "started"]
    launched.clear()
    assert main(["--repo", str(tmp_path)]) == 0
    assert launched == [(tmp_path, None), "started"]


def test_public_module_entry_point():
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "task_harbor", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage: task-harbor" in result.stdout


def test_missing_ui_extra_has_install_hint(tmp_path, monkeypatch, capsys):
    original = builtins.__import__

    def without_textual(name, *args, **kwargs):
        if name == "textual":
            raise ModuleNotFoundError("No module named textual", name="textual")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_textual)
    assert main(["--repo", str(tmp_path), "tui"]) == 2
    assert 'pip install ".[ui]"' in capsys.readouterr().err
    assert not list(tmp_path.iterdir())
