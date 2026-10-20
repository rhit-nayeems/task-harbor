"""Read-only local readiness and saved-run discovery."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import fields
from pathlib import Path

from .backlog import parse_backlog
from .config import Config
from .contracts import load_contracts, unanswered, validate_contract
from .gitops import git
from .models import TaskStatus
from .orchestrator import ManagerError, validate_tasks
from .state import load_state


def read_config(repo: Path) -> Config:
    path = repo / ".manager" / "config.json"
    if not path.exists():
        return Config()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Configuration must be a JSON object")
    names = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in raw.items() if k in names})


def readiness(repo: Path) -> dict:
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    try:
        cfg = read_config(repo)
    except (ValueError, TypeError, OSError) as exc:
        return {"ready": False, "checks": [{"name": "Configuration", "status": "error",
                                           "detail": str(exc)}], "model_calls": 0}
    configured = (repo / ".manager" / "config.json").is_file()
    add("Configuration", "pass" if configured else "warning",
        "Configuration loaded." if configured else "Run task-harbor init to create a configuration.")
    if not shutil.which("git"):
        add("Git", "error", "Install Git and put it on PATH.")
    elif git(repo, "rev-parse", "--verify", "HEAD", check=False).code:
        add("Git", "error", "Use a Git repository with at least one commit.")
    else:
        add("Git", "pass", "Repository has a committed starting point.")
        dirty = bool(git(repo, "status", "--porcelain", check=False).stdout.strip())
        add("Working tree", "warning" if dirty and cfg.allow_dirty_repo else "error" if dirty else "pass",
            "Uncommitted changes exist; commit or stash them before a run." if dirty else "Working tree is clean.")
        identity = all(git(repo, "config", key, check=False).stdout.strip()
                       for key in ("user.name", "user.email"))
        add("Git author", "pass" if identity else "error",
            "Git author is configured." if identity else "Configure git user.name and user.email.")
    binary = cfg.codex_bin if cfg.provider == "codex" else cfg.claude_bin
    add("Agent executable", "pass" if shutil.which(binary) else "error",
        f"{cfg.provider}: executable found; authentication not tested." if shutil.which(binary)
        else f"Install {cfg.provider} or correct its configured executable.")
    for name in cfg.required_executables:
        add(f"Executable: {name}", "pass" if shutil.which(name) else "error",
            "Found on PATH." if shutil.which(name) else "Required executable is missing.")
    for name in cfg.required_env:
        add(f"Environment: {name}", "pass" if os.environ.get(name) else "error",
            "Present (value hidden)." if os.environ.get(name) else "Required variable is missing.")
    add("Verification", "pass" if cfg.verification_commands else "error" if cfg.require_verification else "warning",
        f"{len(cfg.verification_commands)} configured command(s); not executed."
        if cfg.verification_commands else "No checks configured. Add verification_commands before relying on QA.")
    add("Verification policy", "pass" if cfg.require_verification else "warning",
        "Checks are required." if cfg.require_verification else "require_verification is false; missing checks do not stop runs.")
    add("Usage limit", "pass" if cfg.max_agent_calls else "warning",
        f"Run limited to {cfg.max_agent_calls} agent calls." if cfg.max_agent_calls else "No run-wide call limit is configured.")
    try:
        tasks = parse_backlog(repo / cfg.backlog_file)
        validate_tasks(tasks)
        add("Backlog", "pass" if tasks else "error",
            f"{len(tasks)} task(s) validated." if tasks else "Backlog contains no tasks.")
        for task in tasks.values():
            if not task.acceptance_criteria:
                add(f"Acceptance: {task.task_id}", "error", "Add acceptance criteria before starting this task.")
        contracts = load_contracts(repo, cfg.manager_dir)
        for task_id, contract in contracts.items():
            if task_id not in tasks:
                add(f"Agreement: {task_id}", "warning", "No matching backlog task.")
                continue
            validate_contract(contract, len(tasks[task_id].acceptance_criteria))
            pending = unanswered(contract)
            if pending:
                add(f"Agreement: {task_id}", "warning",
                    f"{len(pending)} unanswered question(s); this task will wait for clarification.")
    except (ValueError, TypeError, OSError, ManagerError) as exc:
        add("Backlog / agreements", "error", str(exc))
    return {"ready": not any(c["status"] == "error" for c in checks), "checks": checks,
            "model_calls": 0, "note": "Readiness only: authentication and command outcomes were not tested."}


def saved_runs(repo: Path, status: str | None = None) -> dict:
    cfg = read_config(repo)
    root = repo / cfg.manager_dir / "runs"
    runs, errors = [], []
    for directory in sorted(root.iterdir(), reverse=True) if root.exists() else []:
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            state = load_state(directory / "state.json")
            tasks = list(state.tasks.values())
            complete = sum(t.status == TaskStatus.COMPLETE for t in tasks)
            kind = "complete" if tasks and complete == len(tasks) else "paused" if state.paused else "unfinished"
            item = {"id": directory.name, "status": kind, "provider": state.provider,
                    "completed": complete, "total": len(tasks),
                    "blocked": sum(t.blocked for t in tasks), "stop_reason": state.stop_reason,
                    "branch": state.integration_branch}
            if status is None or status == kind:
                runs.append(item)
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            errors.append({"id": directory.name, "error": str(exc)})
    return {"runs": runs, "errors": errors,
            "note": "Saved snapshots; unfinished does not mean a process is currently running."}


def run_offline(args, repo: Path) -> int:
    result = readiness(repo) if args.command == "check" else saved_runs(repo, args.status)
    if args.json:
        print(json.dumps(result, indent=2))
    elif args.command == "check":
        for item in result["checks"]:
            print(f"{item['status'].upper():7} {item['name']}: {item['detail']}")
        print("Ready for a run." if result["ready"] else "Resolve the errors above before starting.")
        print("No model calls or project commands executed. Authentication is not tested.")
    else:
        for run in result["runs"]:
            print(f"{run['id']}  {run['status']}  {run['completed']}/{run['total']} complete  "
                  f"{run['blocked']} blocked  {run['provider']}")
            if run["stop_reason"]:
                print(f"  {run['stop_reason']}")
        if not result["runs"]:
            print("No saved runs match. Start one with task-harbor manage.")
        for error in result["errors"]:
            print(f"Unreadable run {error['id']}: {error['error']}")
        print(result["note"])
    return 2 if (args.command == "check" and not result["ready"]) or result.get("errors") else 0
