"""Terminal dashboard with explicit project and run controls."""
from __future__ import annotations

import json
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Select, Static, ProgressBar

from .config import Config
from .reporting import run_report
from .help import GUIDE
from .desktop_actions import launch_run
from .reporting import review_text


class ConfirmRun(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    ConfirmRun { align: center middle; background: #000000 70%; }
    #confirm-panel { width: 80%; height: auto; max-height: 90%; border: round #66e3c4; padding: 1 2; background: #111e2c; }
    #confirm-text { height: auto; margin-bottom: 1; }
    """

    def __init__(self, description: str):
        super().__init__()
        self.description = description

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="confirm-panel"):
            yield Static(self.description, id="confirm-text", markup=False)
            yield Button("Start agent work", id="confirm-start", variant="success")
            yield Button("Cancel", id="cancel-start")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-start")


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close"), ("f1", "dismiss", "Close")]
    DEFAULT_CSS = """
    HelpScreen { align: center middle; background: #000000 70%; }
    #help-panel { width: 85%; height: 90%; border: round #66e3c4; padding: 1 2; background: #111e2c; }
    #help-text { height: auto; }
    """

    def __init__(self, content: str = GUIDE):
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-panel"):
            yield Button("Close (Esc)", id="close-help", variant="primary")
            yield Static(self.content, id="help-text", markup=False)

    def on_button_pressed(self) -> None:
        self.dismiss()


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
    BINDINGS = [("f1", "help", "Help"), ("e", "evidence", "Evidence"), ("p", "preflight", "Preflight"), ("q", "quit", "Quit"), ("r", "reload", "Refresh"), ("tab", "focus_next", "Next pane")]
    CSS = """
    Screen { background: #0b111b; color: #d9e4ef; }
    #brand { height: 5; padding: 1 2; background: #111e2c; color: #66e3c4; text-style: bold; }
    #workspace { height: 1; margin: 0 2; color: #8295aa; }
    #actions { height: 3; margin: 1 2 0 2; }
    #actions Button { min-width: 10; width: 1fr; margin-right: 1; }
    #action-result { height: auto; max-height: 5; margin: 0 2; color: #f2c777; }
    #welcome { height: auto; padding: 1 2; margin: 1 2; border: round #66e3c4; background: #111e2c; }
    #completion { height: 1; margin: 0 2; }
    #run-picker { background: #111e2c; }
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
    .compact #brand { height: 3; padding: 0 2; }
    .compact #summary { height: 4; }
    .compact #tasks { width: 1fr; height: 1fr; }
    .compact #details-pane { width: 1fr; height: 6; margin-left: 0; }
    .compact #events { height: 6; }
    """

    def __init__(self, repo: Path, run_id: str | None = None):
        super().__init__()
        self.repo = repo
        self.runs = runs_directory(repo)
        self.selected_run = run_id
        self.report: dict | None = None
        self.run_names: list[str] = []
        self.launched_process = None
        self.launch_log: Path | None = None
        self.action_busy = False
        self.resume_target: str | None = None
        self.awaiting_new_run: set[str] | None = None

    def compose(self) -> ComposeResult:
        yield Static("▰ ▰ ▰  TASK HARBOR\n       Plan → Build → Verify → Review", id="brand")
        yield Static(str(self.repo), id="workspace", markup=False)
        with Horizontal(id="actions"):
            yield Button("Set up", id="setup")
            yield Button("Validate", id="validate")
            yield Button("New run", id="start", variant="success")
            yield Button("Resume", id="resume")
            yield Button("Stop", id="stop", variant="warning")
            yield Button("Review", id="review")
        yield Static("", id="action-result", markup=False)
        yield Static("No runs yet.\n\n1  task-harbor init\n2  Edit BACKLOG.md and .manager/config.json\n3  task-harbor validate\n4  task-harbor manage (in another terminal)\n\nPress F1 for setup help. This dashboard will show the run when it starts.", id="welcome", markup=False)
        yield Select([], prompt="Choose a run", id="run-picker")
        with Horizontal(id="summary"):
            for name in ("progress", "provider", "calls", "cost"):
                yield Static("—", id=name, classes="metric", markup=False)
        yield ProgressBar(total=1, show_eta=False, id="completion")
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

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_evidence(self) -> None:
        if self.report and self.report["tasks"]:
            row = self.query_one(DataTable).cursor_row
            task = self.report["tasks"][min(row, len(self.report["tasks"]) - 1)]
            self.push_screen(HelpScreen(review_text(self.report, task["id"])))
        else:
            self.action_message("Select a saved run and task to inspect its evidence.")

    def action_preflight(self) -> None:
        from .preflight import suggestions
        suggested = suggestions(self.repo)
        self.push_screen(HelpScreen("PROJECT PREFLIGHT\n\nSuggested checks (not executed):\n"
                                    + "\n".join(suggested or ["No known commands detected."])
                                    + "\n\nReview verification_commands, setup_commands, required_env and required_executables in .manager/config.json.\n"
                                    "Then run: task-harbor preflight --run-checks\n\n"
                                    "Set require_verification to true to pause before model calls when baseline checks do not pass."))

    def action_message(self, message: str) -> None:
        self.screen_stack[0].query_one("#action-result", Static).update(message)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "review":
            event.stop()
            self.action_evidence()
            return
        if action not in {"setup", "validate", "start", "resume", "stop"}:
            return
        event.stop()
        if self.action_busy:
            return
        if action in {"start", "resume"}:
            if self.launched_process and self.launched_process.poll() is None:
                self.action_message("A run launched here is still running. Stop it or wait before launching another.")
                return
            try:
                path = self.repo / ".manager" / "config.json"
                if not path.exists():
                    raise ValueError("Use Set up first, then edit the backlog and configuration.")
                raw = json.loads(path.read_text(encoding="utf-8"))
                cfg = Config(**{k: v for k, v in raw.items() if k in Config.__dataclass_fields__})
                self.resume_target = self.selected_run if action == "resume" else None
                if action == "resume" and not self.resume_target:
                    raise ValueError("Select a saved run to resume.")
                verb = f"Resume {self.resume_target}" if self.resume_target else "Start a new run"
                self.push_screen(ConfirmRun(
                    f"{verb}\n\nProject: {self.repo}\nProvider: {cfg.provider}\nModel: {cfg.model}\n"
                    f"Agent call limit: {cfg.max_agent_calls or 'Unlimited'}\n\n"
                    "This starts model calls and changes code in isolated Git worktrees. "
                    "Review your backlog and configuration first.\n\n"
                    "Work continues if you close the dashboard. Stop waits for in-flight calls."
                ), self.confirm_launch)
            except (OSError, ValueError, TypeError) as exc:
                self.action_message(str(exc))
            return
        command = "init" if action == "setup" else action
        args = [sys.executable, "-m", "task_harbor", "--repo", str(self.repo), command]
        if action == "stop":
            if not self.selected_run:
                self.action_message("Select a run to stop.")
                return
            args += ["--run-id", self.selected_run]
        self.action_busy = True
        self.action_message(f"Running {command}…")
        try:
            process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            output, _ = await process.communicate()
            self.action_message(output.decode("utf-8", errors="replace")[-1600:])
            self.runs = runs_directory(self.repo)
        except (OSError, ValueError) as exc:
            self.action_message(str(exc))
        finally:
            self.action_busy = False
            self.action_reload()

    def confirm_launch(self, confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            self.runs = runs_directory(self.repo)
            self.launched_process, self.launch_log = launch_run(self.repo, self.runs, self.resume_target)
            if not self.resume_target:
                self.awaiting_new_run = set(self.run_names)
            self.action_message(f"Agent work launched. Closing this window won't stop it.\nLaunch output: {self.launch_log}")
        except (OSError, ValueError) as exc:
            self.action_message(f"Could not launch: {exc}")

    def on_resize(self) -> None:
        self.screen.set_class(self.size.width < 95, "compact")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != Select.BLANK:
            self.selected_run = str(event.value)
            self.action_reload()

    def action_reload(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        try:
            if self.launched_process and self.launched_process.poll() is not None:
                code = self.launched_process.returncode
                detail = ""
                if code and self.launch_log and self.launch_log.exists():
                    with self.launch_log.open("rb") as stream:
                        stream.seek(0, 2)
                        stream.seek(max(0, stream.tell() - 1000))
                        detail = "\n" + stream.read().decode("utf-8", errors="replace")
                self.action_message(f"Launched process finished (exit {code}). Output: {self.launch_log}{detail}")
                self.launched_process = None
            names = sorted((p.parent.name for p in self.runs.glob("*/state.json")), reverse=True)
            if self.awaiting_new_run is not None:
                created = [name for name in names if name not in self.awaiting_new_run]
                if created:
                    self.selected_run = created[0]
                    self.awaiting_new_run = None
            self.query_one("#run-picker").display = bool(names)
            for button in ("resume", "stop"):
                self.query_one(f"#{button}", Button).disabled = not bool(names)
            if names != self.run_names:
                if self.selected_run in self.run_names and self.selected_run not in names:
                    self.selected_run = names[0] if names else None
                self.run_names = names
                picker = self.query_one(Select)
                picker.set_options([(name, name) for name in names])
                if self.selected_run is None and names:
                    self.selected_run = names[0]
                if self.selected_run in names:
                    picker.value = self.selected_run
            if not self.selected_run:
                config_exists = (self.repo / ".manager" / "config.json").exists()
                self.query_one("#welcome", Static).update(
                    "No runs yet. A run is one execution of your backlog.\n\n"
                    + ("1  Click Set up to create configuration and a sample backlog.\n" if not config_exists else "1  Project configured. Review your backlog and configuration.\n")
                    + "2  Edit BACKLOG.md and .manager/config.json in your editor.\n"
                    "3  Click Validate to check task requirements.\n4  Click New run to review settings and start.\n\n"
                    f"Looking for runs in: {self.runs}\nPress F1 for help."
                )
                self.query_one("#welcome").display = True
                for selector in ("#body", "#events", "#summary", "#completion"):
                    self.query_one(selector).display = False
                self.clear_run("No runs yet.\nStart with: task-harbor --repo <path> init\nEdit BACKLOG.md, then run manage in another terminal.")
                return
            self.query_one("#welcome").display = False
            for selector in ("#body", "#events", "#summary", "#completion"):
                self.query_one(selector).display = True
            self.query_one("#events").display = self.size.height >= 36
            run_dir = self.runs / self.selected_run
            report = run_report(run_dir)
            events = event_tail(run_dir / "events.jsonl")
            updated = datetime.fromtimestamp((run_dir / "state.json").stat().st_mtime).strftime("%H:%M:%S")
            self.query_one("#events", Static).update(events)
            state = "Paused" if report["paused"] else "Complete" if report["completed"] == report["total"] else "Saved state"
            self.query_one("#notice", Static).update(f'{state} · saved {updated} · refreshes every 2s · {report["stop_reason"] or "Viewing saved progress. F1 for help."}')
            if report == self.report:
                return
            table = self.query_one(DataTable)
            row = table.cursor_row
            selected = self.report["tasks"][row]["id"] if self.report and row < len(self.report["tasks"]) else None
            self.report = report
            self.query_one(ProgressBar).update(total=max(1, report["total"]), progress=report["completed"])
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
        self.query_one(ProgressBar).update(total=1, progress=0)
        self.query_one(DataTable).clear()
        for name in ("progress", "provider", "calls", "cost"):
            self.query_one(f"#{name}", Static).update("—")
        self.query_one("#details", Static).update(message)
        self.query_one("#events", Static).update("")
        self.query_one("#notice", Static).update("Viewing is free of model calls. New run / Resume starts agent work after confirmation.")

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
            f'Verification: {task.get("evidence", {}).get("verification_level", "not recorded")}\nPress E for evidence and diff.\n\n'
            + "\n".join(f'{key}: {value:,}' for key, value in tokens.items())
        )
