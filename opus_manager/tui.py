"""Read-only terminal dashboard. Never starts agents or changes run state."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Footer, Select, Static

from .config import Config
from .reporting import run_report


def runs_directory(repo: Path) -> Path:
    # Config.load migrates files; monitoring must remain read-only.
    path = repo / ".manager" / "config.json"
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return repo / Config(manager_dir=raw.get("manager_dir", ".manager")).manager_dir / "runs"


def event_tail(path: Path) -> str:
    """Bound reads even for runs with large event logs; ignore partial last writes."""
    if not path.exists():
        return "No events recorded yet."
    with path.open("rb") as stream:
        stream.seek(0, 2)
        start = max(0, stream.tell() - 16384)
        stream.seek(start)
        lines = stream.read().decode("utf-8", errors="replace").splitlines()
    if start:
        lines = lines[1:]
    events = []
    for line in lines:
        try:
            item = json.loads(line)
            events.append(f'{str(item.get("time", ""))[11:19]}  {item.get("kind", "event")}  {item.get("task_id", "")}')
        except (ValueError, AttributeError):
            continue
    return "\n".join(events[-8:]) or "No events recorded yet."


class HarborApp(App):
    TITLE = "Task Harbor"
    BINDINGS = [("q", "quit", "Quit"), ("r", "reload", "Refresh"), ("tab", "focus_next", "Next pane")]
    CSS = """
    Screen { background: #0b111b; color: #d9e4ef; }
    #brand { height: 5; padding: 1 2; background: #111e2c; color: #66e3c4; text-style: bold; }
    #workspace { height: 1; margin: 0 2; color: #8295aa; }
    #run-picker { margin: 1 2 0 2; }
    #summary { height: 5; margin: 0 2; }
    .metric { width: 1fr; border: round #294158; padding: 0 1; margin-right: 1; }
    #body { height: 1fr; margin: 0 2; }
    #tasks { width: 2fr; height: 1fr; border: round #294158; background: #101b29; }
    #tasks, #details-pane, #events { border-title-color: #66e3c4; }
    #details-pane { width: 1fr; min-width: 25; border: round #294158; margin-left: 1; padding: 0 1; }
    #details { height: auto; }
    #events { height: 11; margin: 0 2; padding: 0 1; border: round #294158; color: #8295aa; }
    #notice { height: auto; max-height: 4; margin: 0 2; color: #f2c777; }
    DataTable > .datatable--cursor { background: #214c52; color: #ffffff; }
    DataTable > .datatable--header { background: #152638; color: #66e3c4; }
    Footer { background: #111e2c; }
    .compact #body { layout: vertical; }
    .compact #tasks { width: 1fr; height: 1fr; }
    .compact #details-pane { width: 1fr; height: 8; margin-left: 0; }
    .compact #events { height: 6; }
    """

    def __init__(self, repo: Path, run_id: str | None = None):
        super().__init__()
        self.repo = repo
        self.runs = runs_directory(repo)
        self.selected_run = run_id
        self.report: dict | None = None
        self.run_names: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("▰ ▰ ▰  TASK HARBOR\n       Plan → Build → Verify → Review", id="brand")
        yield Static(str(self.repo), id="workspace", markup=False)
        yield Select([], prompt="Choose a run", id="run-picker")
        with Horizontal(id="summary"):
            for name in ("progress", "provider", "calls", "cost"):
                yield Static("—", id=name, classes="metric", markup=False)
        with Horizontal(id="body"):
            yield DataTable(id="tasks", cursor_type="row")
            with VerticalScroll(id="details-pane"):
                yield Static("", id="details", markup=False)
        yield Static("", id="events", markup=False)
        yield Static("", id="notice", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Task", "State", "Title")
        table.border_title = "TASKS"
        self.query_one("#details-pane").border_title = "TASK DETAILS"
        self.query_one("#events").border_title = "RECENT EVENTS"
        self.action_reload()
        self.set_interval(2, self.action_reload)
        table.focus()

    def on_resize(self) -> None:
        self.screen.set_class(self.size.width < 95, "compact")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != Select.BLANK:
            self.selected_run = str(event.value)
            self.action_reload()

    def action_reload(self) -> None:
        try:
            names = sorted((p.parent.name for p in self.runs.glob("*/state.json")), reverse=True)
            if names != self.run_names:
                self.run_names = names
                picker = self.query_one(Select)
                picker.set_options([(name, name) for name in names])
                if self.selected_run is None and names:
                    self.selected_run = names[0]
                if self.selected_run in names:
                    picker.value = self.selected_run
            if not self.selected_run:
                self.clear_run("No runs yet.\nStart with: task-harbor --repo <path> init\nEdit BACKLOG.md, then run manage in another terminal.")
                return
            run_dir = self.runs / self.selected_run
            report = run_report(run_dir)
            events = event_tail(run_dir / "events.jsonl")
            updated = datetime.fromtimestamp((run_dir / "state.json").stat().st_mtime).strftime("%H:%M:%S")
            self.query_one("#events", Static).update(events)
            state = "Paused" if report["paused"] else "Complete" if report["completed"] == report["total"] else "Saved state"
            self.query_one("#notice", Static).update(f'{state} · saved {updated} · refreshes every 2s · {report["stop_reason"] or "Monitoring only; run manage/resume in another terminal."}')
            if report == self.report:
                return
            table = self.query_one(DataTable)
            row = table.cursor_row
            selected = self.report["tasks"][row]["id"] if self.report and row < len(self.report["tasks"]) else None
            self.report = report
            usage = report["usage"]
            for name, value in {
                "progress": f'TASKS\n{report["completed"]} / {report["total"]} complete',
                "provider": f'PROVIDER\n{report["provider"].upper()}',
                "calls": f'AGENT CALLS\n{usage["agent_calls"]}',
                "cost": f'REPORTED COST\n${usage["reported_cost_usd"]:.2f}' + (" + unknown" if usage["calls_without_cost"] else ""),
            }.items():
                self.query_one(f"#{name}", Static).update(value)
            table.clear()
            for task in report["tasks"]:
                status = "BLOCKED" if task["blocked_reason"] else task["status"]
                color = "#66e3c4" if status == "COMPLETE" else "#f2c777" if status in {"BLOCKED", "QA_FAIL"} else "#8cbaff"
                table.add_row(Text(task["id"]), Text(status.replace("_", " "), style=color), Text(task["title"]), key=task["id"])
            row = next((i for i, t in enumerate(report["tasks"]) if t["id"] == selected), 0)
            table.move_cursor(row=row)
            self.show_task(row)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self.clear_run(f"Cannot read run data: {exc}\nRetrying in 2s. Press r to retry now.")

    def clear_run(self, message: str) -> None:
        self.report = None
        self.query_one(DataTable).clear()
        for name in ("progress", "provider", "calls", "cost"):
            self.query_one(f"#{name}", Static).update("—")
        self.query_one("#details", Static).update(message)
        self.query_one("#events", Static).update("")
        self.query_one("#notice", Static).update("Read-only dashboard · no model calls")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.show_task(event.cursor_row)

    def show_task(self, row: int) -> None:
        if not self.report or row >= len(self.report["tasks"]):
            return
        task = self.report["tasks"][row]
        tokens = task["usage"]["tokens"]
        self.query_one("#details", Static).update(
            f'{task["id"]}\n{task["title"]}\n\n'
            f'Status: {task["status"]}\nDependencies: {", ".join(task["dependencies"]) or "None"}\n'
            f'Generation: {task["generation"]}\n\n'
            f'Next: {task["next_action"] or "—"}\n'
            f'Blocked: {task["blocked_reason"] or "No"}\n\n'
            f'Checkpoint: {task["checkpoint"] or "—"}\n\n'
            + "\n".join(f'{key}: {value:,}' for key, value in tokens.items())
        )
