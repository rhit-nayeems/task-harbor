"""Capture the real TUI with synthetic data; does not call providers."""
import asyncio
import os
from pathlib import Path
import tempfile

os.environ.pop("NO_COLOR", None)
os.environ["COLORTERM"] = "truecolor"
from opus_manager.models import BacklogTask, ManagerState, TaskStatus
from opus_manager.state import save_state, atomic_write_json
from opus_manager.tui import HarborApp

async def capture():
    destination = Path(__file__).resolve().parents[1] / "docs"
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        app = HarborApp(repo)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            app.query_one("#workspace").update("Example project / search-app (sample data)")
            await pilot.pause()
            (destination / "terminal-welcome.svg").write_text(app.export_screenshot(), encoding="utf-8")
        run = repo / ".manager/runs/example-run"
        run.mkdir(parents=True)
        state = ManagerState("example-run", str(repo), "manager/integration/example-run", "", "main", "abc", provider="codex")
        for ident, title, status in [("API-1", "Add search endpoint", TaskStatus.COMPLETE), ("UI-2", "Show search results", TaskStatus.IMPLEMENTING), ("QA-3", "Test empty results", TaskStatus.READY), ("DOC-4", "Document search options", TaskStatus.UNPLANNED)]:
            state.tasks[ident] = BacklogTask(ident, title, status=status, next_action="Run acceptance checks", dependencies=["API-1"] if ident != "API-1" else [])
        save_state(run / "state.json", state)
        atomic_write_json(run / "usage.json", {"calls": [{"task": "UI-2", "usage": {"input_tokens": 12000, "output_tokens": 3200}}] * 6})
        (run / "events.jsonl").write_text('{"time":"2026-10-19T14:30:00Z","kind":"QA_PASSED","task_id":"API-1"}\n{"time":"2026-10-19T14:31:00Z","kind":"IMPLEMENTATION_STARTED","task_id":"UI-2"}')
        app = HarborApp(repo)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            await pilot.press("down")
            app.query_one("#workspace").update("Example project / search-app (sample data)")
            await pilot.pause()
            (destination / "terminal-dashboard.svg").write_text(app.export_screenshot(), encoding="utf-8")
            await pilot.press("e")
            await pilot.pause()
            (destination / "terminal-evidence.svg").write_text(app.export_screenshot(), encoding="utf-8")
            await pilot.press("escape")
            await pilot.press("f1")
            await pilot.pause()
            (destination / "terminal-help.svg").write_text(app.export_screenshot(), encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(capture())
