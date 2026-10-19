from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backlog import parse_backlog, write_template
from .config import Config
from .gitops import ensure_repo, git
from .orchestrator import ManagerError, Orchestrator, validate_tasks
from .state import load_state, atomic_write_json
from .reporting import run_report, write_html
from .models import TaskStatus


def _repo(value: str) -> Path:
    p = Path(value).expanduser().resolve()
    if not p.exists():
        raise argparse.ArgumentTypeError(f"Path does not exist: {p}")
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="task-harbor",
        description="Multi-provider backlog orchestrator with isolated planning, implementation, QA, escalation, and code review.",
    )
    p.add_argument("--repo", type=_repo, default=Path.cwd(), help="Target Git repository (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)
    tui = sub.add_parser("tui", help="Open the live terminal dashboard (install the ui extra)")
    tui.add_argument("--run-id", help="Select a saved run")

    sub.add_parser("init", help="Create .manager/config.json and a BACKLOG.md template if absent")
    sub.add_parser("doctor", help="Validate Git, backlog, configuration, and agent CLI connectivity")
    sub.add_parser("validate", help="Validate backlog structure and dependency graph without running agents")

    manage = sub.add_parser("manage", help="Start a new autonomous manager run")
    manage.add_argument("--backlog", type=Path, default=None, help="Backlog path (default: config backlog_file)")

    resume = sub.add_parser("resume", help="Resume an existing manager run")
    resume.add_argument("--run-id", required=True)

    status = sub.add_parser("status", help="Show persisted state for a run")
    status.add_argument("--run-id", required=True)

    cleanup = sub.add_parser("cleanup", help="Remove linked worktrees for a finished/abandoned run; branches are retained")
    cleanup.add_argument("--run-id", required=True)
    for name in ("stop", "report", "retry"):
        command = sub.add_parser(name, help={"stop": "Stop at the next agent boundary", "report": "Offline JSON or HTML run report", "retry": "Explicitly retry a blocked task"}[name])
        command.add_argument("--run-id", required=True)
        if name == "report":
            command.add_argument("--html", type=Path, help="Write an offline HTML dashboard")
        if name == "retry":
            command.add_argument("--task", required=True)
    return p


def load_config(repo: Path) -> Config:
    path = repo / ".manager" / "config.json"
    return Config.load(path)


def cmd_init(repo: Path) -> int:
    ensure_repo(repo)
    cfg = load_config(repo)
    backlog = repo / cfg.backlog_file
    if not backlog.exists():
        write_template(backlog)
        print(f"Created {backlog}")
    else:
        print(f"Kept existing {backlog}")
    print(f"Config: {repo / cfg.manager_dir / 'config.json'}")
    print("Next: edit BACKLOG.md, then run `opus-manager --repo <repo> doctor`.")
    return 0


def cmd_validate(repo: Path, cfg: Config) -> int:
    ensure_repo(repo)
    tasks = parse_backlog(repo / cfg.backlog_file)
    validate_tasks(tasks)
    blocked = []
    for t in tasks.values():
        missing = [d for d in t.dependencies if tasks[d].status.value != "COMPLETE"]
        if missing:
            blocked.append((t.task_id, missing))
    print(f"Valid backlog: {len(tasks)} task(s)")
    if blocked:
        print("Currently dependency-blocked:")
        for tid, deps in blocked:
            print(f"  {tid}: {', '.join(deps)}")
    return 0


def cmd_doctor(repo: Path, cfg: Config) -> int:
    cmd_validate(repo, cfg)
    # A transient throwaway run object is unnecessary; invoke Claude through a small temporary run context.
    from .providers import create_client
    hooks = repo / cfg.manager_dir / "doctor-hooks"
    client = create_client(cfg, hooks)
    result = client.probe(repo)
    if result.text.strip().upper() != "OK":
        raise ManagerError(f"Agent probe failed: {result.text}")
    print(f"{cfg.provider} CLI: OK (model={cfg.model}, effort={cfg.effort})")
    print(f"Git branch: {git(repo, 'branch', '--show-current').stdout}")
    print("Doctor checks passed.")
    return 0


def cmd_status(repo: Path, cfg: Config, run_id: str) -> int:
    state_file = repo / cfg.manager_dir / "runs" / run_id / "state.json"
    if not state_file.exists():
        raise ManagerError(f"Run not found: {run_id}")
    state = load_state(state_file)
    print(f"Run: {state.run_id}")
    print(f"Integration branch: {state.integration_branch}")
    print(f"QA passes since review: {state.qa_passes_since_review}")
    print(f"Paused: {state.paused}")
    if state.stop_reason:
        print(f"Stop reason: {state.stop_reason}")
    print("Usage: " + json.dumps(run_report(state_file.parent)["usage"]))
    print("Tasks:")
    for t in state.tasks.values():
        blocked = f" | blocked: {t.blocked_reason}" if t.blocked_reason else ""
        print(f"  {t.task_id:16} {t.status.value:12} {t.priority.value:14}{blocked}")
    return 0


def cmd_cleanup(repo: Path, cfg: Config, run_id: str) -> int:
    state_file = repo / cfg.manager_dir / "runs" / run_id / "state.json"
    if not state_file.exists():
        raise ManagerError(f"Run not found: {run_id}")
    manager = Orchestrator.resume(repo, cfg, run_id)
    manager._acquire_run_lock()
    try:
        state = load_state(state_file)
        from .gitops import worktree_remove
        root = manager.paths.worktrees_root.resolve()
        candidates = [Path(t.worktree_path) for t in state.tasks.values() if t.worktree_path]
        candidates.append(Path(state.integration_worktree))
        for path in candidates:
            if not path.resolve().is_relative_to(root):
                raise ManagerError(f"Refusing cleanup outside run worktree root: {path}")
        for path in candidates:
            worktree_remove(repo, path, force=True)
    finally:
        manager._release_run_lock()
    print("Linked worktrees removed. Local branches and run artifacts were retained.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "init":
            return cmd_init(repo)
        if getattr(args, "run_id", None) is not None and (not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.run_id)):
            raise ValueError("Invalid run ID")
        if args.command == "tui":
            try:
                import textual  # Check the optional extra before importing its dependencies.
                from .tui import HarborApp
            except ModuleNotFoundError as exc:
                if exc.name != "textual":
                    raise
                raise ManagerError('Install the dashboard first: python -m pip install ".[ui]" (from the Task Harbor checkout)') from exc
            HarborApp(repo, args.run_id).run()
            return 0
        cfg = load_config(repo)
        if args.command in {"report", "stop", "retry"}:
            run_dir = repo / cfg.manager_dir / "runs" / args.run_id
            if not (run_dir / "state.json").exists():
                raise ManagerError(f"Run not found: {args.run_id}")
            if args.command == "report":
                report = run_report(run_dir)
                if args.html:
                    write_html(report, args.html)
                    print(f"Report: {args.html.resolve()}")
                else:
                    print(json.dumps(report, indent=2))
                return 0
            if args.command == "stop":
                atomic_write_json(run_dir / "stop-request.json", {"requested": True})
                print("Stop requested. In-flight calls finish; no new calls will start.")
                return 0
            manager = Orchestrator.resume(repo, cfg, args.run_id)
            manager._acquire_run_lock()
            try:
                manager.state = load_state(run_dir / "state.json")
                task = manager.state.tasks.get(args.task)
                if task is None or not task.blocked:
                    raise ManagerError("retry requires an existing blocked task")
                manager._recover_interrupted_tasks()
                needs_review = task.metadata.get("blocked_kind") == "plan_rework_limit"
                task.blocked_reason = None
                task.metadata.pop("blocked_kind", None)
                task.qa_failures = 0
                task.generation = 0
                task.plan_reworks = 0
                task.implementer_session_id = None
                task.status = (TaskStatus.PLAN_REVIEW if needs_review else TaskStatus.READY) if task.plan_path else TaskStatus.UNPLANNED
                task.metadata["resume_mode"] = "implementation"
                manager._event("OPERATOR_RETRY", task_id=task.task_id)
                manager._sync_backlog()
            finally:
                manager._release_run_lock()
            print("Task retry recorded. Resume the run to continue; usage budgets remain cumulative.")
            return 0
        if args.command == "validate":
            return cmd_validate(repo, cfg)
        if args.command == "doctor":
            return cmd_doctor(repo, cfg)
        if args.command == "manage":
            backlog = args.backlog
            if backlog is not None and not backlog.is_absolute():
                backlog = repo / backlog
            manager = Orchestrator.start(repo, cfg, backlog)
            print(f"Run ID: {manager.state.run_id}")
            print(f"Integration branch: {manager.state.integration_branch}")
            manager.run()
            print(f"Stopped: {manager.state.stop_reason}")
            return 0 if not manager.state.paused else 2
        if args.command == "resume":
            manager = Orchestrator.resume(repo, cfg, args.run_id)
            manager.run()
            print(f"Stopped: {manager.state.stop_reason}")
            return 0 if not manager.state.paused else 2
        if args.command == "status":
            return cmd_status(repo, cfg, args.run_id)
        if args.command == "cleanup":
            return cmd_cleanup(repo, cfg, args.run_id)
        raise ManagerError(f"Unknown command: {args.command}")
    except (ManagerError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
