import asyncio
import json

import pytest

pytest.importorskip("textual")
from textual.widgets import DataTable, Static, Select

from opus_manager.models import BacklogTask, ManagerState, TaskStatus
from opus_manager.state import save_state
from opus_manager.tui import HarborApp, event_tail, runs_directory


def write_run(repo, name="run-001"):
    state = ManagerState(name, str(repo), "manager/integration/" + name, "", "main", "abc")
    state.tasks = {"API-1": BacklogTask("API-1", "Add search endpoint"),
                   "UI-2": BacklogTask("UI-2", "Show search results", dependencies=["API-1"])}
    path = repo / ".manager" / "runs" / name
    path.mkdir(parents=True)
    save_state(path / "state.json", state)
    return path, state


def test_empty_dashboard_does_not_write(tmp_path):
    async def check():
        app = HarborApp(tmp_path)
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            assert "No runs yet" in str(app.query_one("#details", Static).render())
            assert app.screen.has_class("compact")
            await pilot.press("q")
        assert not list(tmp_path.iterdir())
    asyncio.run(check())


def test_navigation_refresh_switch_and_error_recovery(tmp_path):
    path, state = write_run(tmp_path)
    (path / "usage.json").write_text(json.dumps({"calls": [{"task": "API-1", "usage": {"input_tokens": 100}}]}))
    async def check():
        app = HarborApp(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one(DataTable).row_count == 2
            assert "unknown" in str(app.query_one("#cost", Static).render())
            await pilot.press("down")
            assert "UI-2" in str(app.query_one("#details", Static).render())
            state.tasks["UI-2"].status = TaskStatus.COMPLETE
            save_state(path / "state.json", state)
            await pilot.press("r")
            assert app.report["completed"] == 1
            assert app.query_one(DataTable).cursor_row == 1
            (path / "state.json").write_text("{")
            await pilot.press("r")
            assert app.report is None
            assert "Cannot read" in str(app.query_one("#details", Static).render())
            save_state(path / "state.json", state)
            write_run(tmp_path, "run-002")
            await pilot.press("r")
            app.query_one(Select).value = "run-002"
            await pilot.pause()
            assert app.report["run_id"] == "run-002"
    asyncio.run(check())


def test_custom_directory_and_event_tail(tmp_path):
    (tmp_path / ".manager").mkdir()
    config = tmp_path / ".manager" / "config.json"
    config.write_text('{"manager_dir": "runs-data"}')
    assert runs_directory(tmp_path) == tmp_path / "runs-data" / "runs"
    assert config.read_text() == '{"manager_dir": "runs-data"}'
    events = tmp_path / "events.jsonl"
    events.write_text("x" * 20000 + '\n{"kind":"QA_PASSED","task_id":"API-1"}\n{"partial":')
    assert "QA_PASSED" in event_tail(events)
    assert "partial" not in event_tail(events)
