"""Local operator actions; no model calls."""
import json
import math
from datetime import datetime, timezone

from .backlog import parse_backlog
from .contracts import load_contracts, validate_contract, unanswered
from .gitops import head, ensure_repo
from .orchestrator import Orchestrator
from .preflight import baseline, suggestions
from .reporting import run_report, write_html, review_text
from .state import atomic_write_json, load_state


def run_operator_command(args, repo, cfg):
    root = repo / cfg.manager_dir
    if args.command == "preflight":
        ensure_repo(repo)
        if not args.run_checks:
            print(json.dumps({"suggestions_not_executed": suggestions(repo), "approved_commands": cfg.verification_commands,
                              "setup_commands": cfg.setup_commands,
                              "next": "Edit .manager/config.json, then preflight --run-checks"}, indent=2))
            return 0
        result = baseline(repo, cfg, head(repo))
        atomic_write_json(root / "preflight.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 2
    if args.command == "contract":
        tasks = parse_backlog(repo / cfg.backlog_file)
        if args.task not in tasks:
            raise ValueError("Task not found in backlog")
        contract = validate_contract(json.loads(args.file.read_text(encoding="utf-8")), len(tasks[args.task].acceptance_criteria))
        contracts = load_contracts(repo, cfg.manager_dir)
        contracts[args.task] = contract
        atomic_write_json(root / "contracts.json", contracts)
        print("Agreement saved for future runs. Existing runs keep their saved agreement.")
        return 0
    run_dir = root / "runs" / args.run_id
    if args.command == "review":
        report = run_report(run_dir)
        if args.html:
            if args.task:
                report["tasks"] = [t for t in report["tasks"] if t["id"] == args.task]
                if not report["tasks"]:
                    raise ValueError("Task not found")
            write_html(report, args.html)
            print(f"Review: {args.html.resolve()}")
        else:
            print(review_text(report, args.task))
        return 0
    if args.command == "questions":
        state = load_state(run_dir / "state.json")
        print(json.dumps({t.task_id: unanswered(t.metadata.get("contract", {})) for t in state.tasks.values()
                          if unanswered(t.metadata.get("contract", {}))}, indent=2))
        return 0
    manager = Orchestrator.resume(repo, cfg, args.run_id)
    manager._acquire_run_lock()
    try:
        manager.state = load_state(run_dir / "state.json")
        task = manager.state.tasks.get(args.task)
        if task is None:
            raise ValueError("Task not found")
        if args.command == "answer":
            contract = task.metadata.get("contract", {})
            if args.question not in contract.get("questions", {}) or not args.text.strip():
                raise ValueError("Supply a known question ID and a nonempty answer")
            contract.setdefault("answers", {})[args.question] = args.text
            if not unanswered(contract) and task.metadata.get("blocked_kind") == "clarification":
                task.blocked_reason = None
                task.metadata.pop("blocked_kind", None)
            manager._event("OPERATOR_ANSWER", task_id=args.task, question_id=args.question)
            manager._sync_backlog()
            print("Answer saved. Resume the run to continue.")
        else:
            if not math.isfinite(args.minutes) or args.minutes < 0:
                raise ValueError("Review minutes must be finite and nonnegative")
            path = run_dir / "feedback.json"
            entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            entries.append({"task": args.task, "outcome": args.outcome, "active_review_minutes": args.minutes,
                            "note": args.note, "checkpoint": task.checkpoint_commit,
                            "time": datetime.now(timezone.utc).isoformat()})
            atomic_write_json(path, entries)
            print("Review feedback saved; task status was not changed.")
    finally:
        manager._release_run_lock()
    return 0
