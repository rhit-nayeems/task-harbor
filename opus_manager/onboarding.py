"""First-run configuration and an explicitly scripted, provider-free example."""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from .backlog import render_backlog, write_template
from .config import Config
from .evidence import change_evidence
from .gitops import ensure_local_exclude, ensure_repo, git, head
from .models import BacklogTask, ManagerState, TaskStatus
from .offline import read_config
from .preflight import suggestions
from .reporting import review_summary, run_report, write_html
from .state import atomic_write_json, save_state
from .verification import run_checks


def setup(repo: Path, args) -> int:
    ensure_repo(repo)
    cfg = read_config(repo)  # Reading an existing configuration must not migrate it yet.
    path = repo / ".manager/config.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    interactive = sys.stdin.isatty()

    def choose(value, question, default=None):
        if value is not None:
            return value
        if not interactive:
            if default is not None:
                return default
            raise ValueError("Supply --provider, --model and --check, or run setup in an interactive terminal.")
        answer = input(f"{question}" + (f" [{default}]" if default is not None else "") + ": ").strip()
        return answer or default

    provider = choose(args.provider, "Provider (claude/codex)", cfg.provider)
    # Do not silently carry a Claude model into a Codex configuration.
    model_default = cfg.model if provider == cfg.provider else None
    model = choose(args.model, "Model available in your account", model_default)
    commands = args.check or cfg.verification_commands
    if not commands:
        hints = suggestions(repo)
        if hints:
            print("Detected commands (not executed): " + ", ".join(hints))
        commands = [choose(None, "Test/check command")]
    if not all(isinstance(c, str) and c.strip() for c in commands):
        raise ValueError("At least one nonempty verification command is required.")
    limit = args.max_agent_calls
    if limit is None:
        limit = int(choose(None, "Maximum agent calls per run", cfg.max_agent_calls or 20))
    values = asdict(cfg)
    values.update(provider=provider, model=model, verification_commands=commands,
                  require_verification=True, max_agent_calls=limit)
    if provider != cfg.provider:
        values.update(effort="medium", max_run_cost_usd=None, max_call_cost_usd=None)
    configured = Config(**values)  # Validate everything before writing anything.
    ensure_local_exclude(repo, ".manager")
    if configured.manager_dir != ".manager":
        ensure_local_exclude(repo, configured.manager_dir)
    backlog = repo / configured.backlog_file
    if not backlog.exists():
        backlog.parent.mkdir(parents=True, exist_ok=True)
        write_template(backlog)
    atomic_write_json(path, {**existing, **asdict(configured)})
    print(f"Saved {path}. Required checks: {len(commands)}. Run call limit: {limit}.")
    print("Harbor's local files are excluded through Git's local info/exclude; .gitignore was not changed.")
    print(f"1. Replace the sample task in {configured.backlog_file} with one small, observable change.")
    print("2. Run task-harbor check and resolve errors. Authentication is not tested.")
    print("3. Commit your project changes, then run task-harbor preflight --run-checks.")
    print("4. Run task-harbor manage when ready to use your provider account.")
    print("No model calls or verification commands were executed. Call limits are not token or dollar limits.")
    return 0


def demo(output: Path | None = None) -> int:
    repo = output.expanduser().absolute() if output else Path(tempfile.mkdtemp(prefix="task-harbor-demo-"))
    if output:
        repo.mkdir(parents=True, exist_ok=False)  # Never overwrite an existing directory.
    print(f"Sample repository: {repo}")
    print("Scripted demonstration: no agents, authentication, or model usage. Tests and Git commits are real.")
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Task Harbor demo")
    git(repo, "config", "user.email", "demo@example.invalid")
    (repo / ".gitignore").write_text(".manager/\n__pycache__/\nreview.html\n", encoding="utf-8")
    source = repo / "search.py"
    source.write_text("def search(query):\n    return query.split()[0]\n", encoding="utf-8")
    (repo / "test_search.py").write_text(
        "import unittest\nfrom search import search\n\nclass SearchTests(unittest.TestCase):\n"
        "    def test_empty(self):\n        self.assertEqual(search(''), 'No results')\n"
        "    def test_normal(self):\n        self.assertEqual(search('hello world'), 'hello')\n", encoding="utf-8")
    task = BacklogTask("BUG-001", "Handle an empty search", acceptance_criteria=[
        "Empty queries return 'No results'; normal queries still return their first word."])
    render_backlog(repo / "BACKLOG.md", {task.task_id: task})
    git(repo, "add", ".")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "Sample search with an empty-query bug")
    base = head(repo)
    branch = "manager/integration/demo-001"
    git(repo, "checkout", "-b", branch)
    command = f'"{sys.executable}" -m unittest -v'
    before = run_checks([command], repo, timeout=30, limit=12000)
    print("1. Reproduced the bug: " + ("FAIL (expected)" if before[0]["exit_code"] else "unexpected PASS"))
    source.write_text("def search(query):\n    words = query.split()\n    return words[0] if words else 'No results'\n", encoding="utf-8")
    git(repo, "add", "search.py")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "Handle empty queries")
    checkpoint = head(repo)
    checks = run_checks([command], repo, timeout=30, limit=12000)
    if before[0]["exit_code"] == 0 or checks[0]["exit_code"] != 0:
        raise RuntimeError("Demo checks did not produce the expected failure followed by a pass; inspect test_search.py.")
    print("2. Applied the scripted fix; both tests pass at the recorded checkpoint.")
    cfg = Config(verification_commands=[command], require_verification=True, max_agent_calls=20)
    run_dir = repo / ".manager/runs/demo-001"
    evidence_path = run_dir / "qa.json"
    atomic_write_json(evidence_path, {
        "checkpoint_commit": checkpoint, "verification_level": "deterministic_checks_only",
        "summary": "The scripted fix handles empty input without changing normal search behavior.",
        "harness_checks": checks, "acceptance": [{"criterion_id": "AC-1", "criterion": task.acceptance_criteria[0],
            "status": "PASS", "evidence": "test_empty and test_normal passed in the local unittest run."}],
        "reproduction": {"before": {"status": "FAIL", "checks": before}, "after": checks},
        "changes": change_evidence(repo, base, checkpoint, cfg),
        "risks": ["Scripted example only. No model QA ran. These two tests do not establish production correctness."]})
    task.status = TaskStatus.COMPLETE
    task.checkpoint_commit = checkpoint
    task.last_qa_path = str(evidence_path)
    task.next_action = "Inspect the diff and record your human review."
    state = ManagerState("demo-001", str(repo), branch, str(repo), "main", base,
                         tasks={task.task_id: task}, stop_reason="Scripted demo finished; human review pending.")
    save_state(run_dir / "state.json", state)
    cfg.save(repo / ".manager/config.json")
    report = run_report(run_dir)
    write_html(report, repo / "review.html")
    print("3. Review the evidence:\n" + "\n".join(review_summary(report["tasks"][0], [])))
    print(f'\nOpen {repo / "review.html"} in your browser, or explore the dashboard:')
    print(f'task-harbor --repo "{repo}" tui --run-id demo-001')
    print(f'Full checks and diff: task-harbor --repo "{repo}" review --run-id demo-001')
    print(f'For your own project: task-harbor --repo "path/to/project" setup')
    return 0
