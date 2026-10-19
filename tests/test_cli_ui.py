import builtins

from opus_manager.cli import main


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
