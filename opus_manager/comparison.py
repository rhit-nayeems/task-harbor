"""Opt-in unattended comparisons. Preparation never starts providers or graders."""
from __future__ import annotations

import json
import platform
import random
import shutil
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from .backlog import render_backlog
from .config import Config
from .contracts import validate_contract, unanswered
from .gitops import git, remote_block_env, ensure_local_exclude
from .models import BacklogTask
from .orchestrator import Orchestrator
from .preflight import baseline, execute_checks
from .providers import create_client
from .state import atomic_write_json
from .usage import UsageLedger, summarize
from .verification import run_checks


def validate_manifest(raw: dict, manifest: Path) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Comparison manifest must be an object")
    if not isinstance(raw.get("repo"), str) or not isinstance(raw.get("commit"), str):
        raise ValueError("Comparison needs repo and commit strings")
    repo = (manifest.parent / raw["repo"]).resolve()
    commit = git(repo, "rev-parse", "--verify", str(raw["commit"]) + "^{commit}").stdout
    cfg = Config(**raw.get("config", {}))
    tasks = raw.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Comparison needs at least one task")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task must be an object")
        tid = task.get("id", "")
        if not isinstance(tid, str) or not tid or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in tid) or tid in seen:
            raise ValueError("Task IDs must be unique path-safe identifiers")
        seen.add(tid)
        if not isinstance(task.get("title"), str) or not task["title"].strip():
            raise ValueError("Each task needs a title")
        for key in ("acceptance_criteria", "grader_commands"):
            values = task.get(key)
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"Each task needs nonempty {key}")
        contract = validate_contract(task.get("contract", {}), len(task["acceptance_criteria"]))
        if unanswered(contract):
            raise ValueError("Resolve all contract questions before comparing implementations")
    return {"repo": str(repo), "commit": commit, "config": asdict(cfg), "tasks": tasks}


def compare(manifest: Path, output: Path, *, live=False, repetitions=1) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    spec = validate_manifest(json.loads(manifest.read_text(encoding="utf-8")), manifest)
    output.mkdir(parents=True, exist_ok=False)
    schedule = [(task["id"], repetition, arm) for task in spec["tasks"]
                for repetition in range(repetitions) for arm in ("direct", "harbor")]
    random.Random(0).shuffle(schedule)
    atomic_write_json(output / "manifest.json", spec)
    atomic_write_json(output / "schedule.json", schedule)
    if not live:
        return {"status": "prepared", "output": str(output), "trials": len(schedule),
                "model_calls": 0, "note": "Use --live with a new output directory to execute. Graders are operator-trusted shell commands."}
    cfg = Config(**spec["config"])
    results = []
    source = Path(spec["repo"])
    binary = cfg.codex_bin if cfg.provider == "codex" else cfg.claude_bin
    from .codex import executable_command
    try:
        command = executable_command(binary) if cfg.provider == "codex" else [shutil.which(binary) or binary]
        version_result = subprocess.run(command + ["--version"], capture_output=True, text=True, timeout=15)
        provider_version = version_result.stdout.strip() if version_result.returncode == 0 else "unavailable"
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        provider_version = "unavailable"
    for task_id, repetition, arm in schedule:
        task_spec = next(t for t in spec["tasks"] if t["id"] == task_id)
        trial = output / f"{task_id}-{repetition}-{arm}"
        trial.mkdir()
        repo = trial / "repo"
        row = {"task": task_id, "repetition": repetition, "arm": arm,
               "provider": cfg.provider, "model": cfg.model, "base_commit": spec["commit"],
               "platform": platform.platform(), "python": platform.python_version(),
               "provider_cli_version": provider_version,
               "human_active_minutes": None, "human_outcome": None,
               "accepted": False, "error": None}
        started = time.monotonic()
        try:
            git(source, "clone", "--no-local", "--no-hardlinks", str(source), str(repo), timeout=300)
            git(repo, "checkout", "-b", "harbor-comparison", spec["commit"])
            for key in ("user.name", "user.email"):
                value = git(source, "config", "--get", key).stdout
                git(repo, "config", key, value)
            task = BacklogTask(task_id, task_spec["title"], acceptance_criteria=task_spec["acceptance_criteria"])
            task.metadata["contract"] = task_spec.get("contract", {})
            render_backlog(repo / cfg.backlog_file, {task_id: task})
            git(repo, "add", "--", cfg.backlog_file)
            git(repo, "commit", "--allow-empty", "-m", "Prepare comparison task")
            ensure_local_exclude(repo, cfg.manager_dir)
            atomic_write_json(repo / cfg.manager_dir / "contracts.json", {task_id: task.metadata["contract"]})
            row["baseline"] = baseline(repo, cfg, spec["commit"])
            env = remote_block_env(trial / "hooks")
            if row["baseline"]["status"] == "ENVIRONMENT_BLOCKED":
                raise RuntimeError("Baseline environment blocked")
            if cfg.require_verification and row["baseline"]["status"] != "PASS":
                raise RuntimeError("Required baseline verification did not pass")
            agent_started = time.monotonic()
            if arm == "harbor":
                manager = Orchestrator.start(repo, cfg)
                manager.run()
                candidate = Path(manager.state.integration_worktree)
                row["manager_stop_reason"] = manager.state.stop_reason
                row["usage"] = summarize(manager.usage.read())
            else:
                environment = execute_checks(cfg, repo, env)
                if environment["status"] == "ENVIRONMENT_BLOCKED":
                    raise RuntimeError("Direct environment blocked")
                client = create_client(cfg, trial / "hooks")
                ledger = UsageLedger(trial / "usage.json", cfg)
                call_id, cap = ledger.reserve("implementer", task_id)
                # A single direct invocation contains the provider's normal tool loop.
                # It receives the task and approved checks, not the independent grader.
                prompt = "Implement this task, inspect the repository, run the approved checks, and repair failures. Do not push or publish.\n" + json.dumps({
                    "title": task.title, "acceptance_criteria": task.acceptance_criteria,
                    "contract": task.metadata["contract"], "verification_commands": cfg.verification_commands}, indent=2)
                kwargs = {"cwd": repo, "role": "implementer", "max_turns": cfg.max_turns_implementer, "env": env}
                if cfg.provider == "claude" and cap is not None:
                    kwargs["budget_usd"] = cap
                try:
                    response = client.run(prompt, **kwargs)
                    ledger.finish(call_id, response.raw)
                    (trial / "direct-response.txt").write_text(response.text, encoding="utf-8")
                except Exception as exc:
                    ledger.finish(call_id, getattr(exc, "raw", None), str(exc))
                    raise
                row["usage"] = summarize(ledger.read())
                candidate = repo
            row["agent_elapsed_seconds"] = round(time.monotonic() - agent_started, 3)
            row["independent_checks"] = run_checks(task_spec["grader_commands"], candidate,
                timeout=cfg.verification_timeout_seconds, limit=cfg.evidence_max_chars, env=env)
            row["accepted"] = (len(row["independent_checks"]) == len(task_spec["grader_commands"])
                               and all(c["exit_code"] == 0 and not c["timed_out"] for c in row["independent_checks"]))
        except Exception as exc:
            row["error"] = str(exc)
        row["elapsed_seconds"] = round(time.monotonic() - started, 3)
        # Persist every failed or successful trial, not just the winners.
        for ledger_path in [trial / "usage.json", *repo.glob(f"{cfg.manager_dir}/runs/*/usage.json")]:
            if "usage" not in row and ledger_path.exists():
                row["usage"] = summarize(json.loads(ledger_path.read_text(encoding="utf-8")))
        atomic_write_json(trial / "result.json", row)
        results.append(row)
        atomic_write_json(output / "results.json", results)
    summary = {arm: {"attempts": sum(r["arm"] == arm for r in results),
                     "independently_passing": sum(r["arm"] == arm and r["accepted"] for r in results),
                     "errors": sum(r["arm"] == arm and r["error"] is not None for r in results)} for arm in ("direct", "harbor")}
    atomic_write_json(output / "summary.json", summary)
    return summary
