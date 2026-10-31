"""First-run configuration and an explicitly scripted, provider-free example."""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from .backlog import parse_backlog, render_backlog, write_template
from .config import Config
from .evidence import change_evidence
from .gitops import ensure_local_exclude, ensure_repo, git, head
from .models import BacklogTask, ManagerState, TaskStatus
from .offline import read_config
from .preflight import suggestions
from .reporting import review_summary, run_report, write_html
from .state import atomic_write_json, save_state
from .verification import run_checks


def new_task(task_id, title, criteria) -> BacklogTask:
    if not isinstance(task_id, str) or not task_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in task_id):
        raise ValueError("Use a nonempty task ID containing letters, digits, hyphens, or underscores.")
    if not isinstance(title, str) or not title.strip() or "\n" in title or "\r" in title:
        raise ValueError("Provide a one-line task title.")
    if not criteria or any(not isinstance(c, str) or not c.strip() or "\n" in c or "\r" in c for c in criteria):
        raise ValueError("Provide at least one observable, one-line acceptance criterion.")
    return BacklogTask(task_id, title.strip(), acceptance_criteria=[c.strip() for c in criteria], next_action="Plan the task")


def existing_tasks(path: Path):
    if not path.exists() or not any(line.startswith("##") for line in path.read_text(encoding="utf-8").splitlines()):
        return {}
    return parse_backlog(path)


def append_task(path: Path, task: BacklogTask) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Backlog\n"
    if task.task_id in existing_tasks(path):
        raise ValueError(f"Task already exists: {task.task_id}")
    with tempfile.TemporaryDirectory() as directory:
        rendered = Path(directory) / "task.md"
        render_backlog(rendered, {task.task_id: task})
        block = "## " + rendered.read_text(encoding="utf-8").split("## ", 1)[1]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")


def next_task_id(path: Path) -> str:
    try:
        tasks = existing_tasks(path)
    except ValueError:
        # Keep the setup form usable; saving still validates the existing file.
        tasks = {}
    number = 1
    while f"TASK-{number:03}" in tasks:
        number += 1
    return f"TASK-{number:03}"


def collect_task(args, interactive: bool, default_id="TASK-001") -> BacklogTask:
    task_id, title, criteria = args.task_id, args.title, args.accept
    if interactive:
        task_id = task_id or input(f"Task ID [{default_id}]: ").strip() or default_id
        title = title or input("What small change should the agent make? ").strip()
        if not criteria:
            print("Acceptance criteria: one observable result per line; blank line finishes.")
            criteria = []
            while value := input(f"Criterion {len(criteria) + 1}: ").strip():
                criteria.append(value)
    return new_task(task_id, title, criteria)


def add_task(repo: Path, args) -> int:
    ensure_repo(repo)
    path = repo / read_config(repo).backlog_file
    task = collect_task(args, sys.stdin.isatty(), next_task_id(path))
    append_task(path, task)
    print(f"Added {task.task_id} to {path}. Existing runs keep their saved requirements.")
    print("Next: task-harbor check. Commit project changes and run preflight --run-checks before manage.")
    return 0


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
    backlog = repo / configured.backlog_file
    task = None
    if getattr(args, "title", None) or getattr(args, "task_id", None) or getattr(args, "accept", None) or (interactive and not existing_tasks(backlog)):
        task = collect_task(args, interactive, next_task_id(backlog))
        if task.task_id in existing_tasks(backlog):
            raise ValueError(f"Task already exists: {task.task_id}")
    ensure_local_exclude(repo, ".manager")
    if configured.manager_dir != ".manager":
        ensure_local_exclude(repo, configured.manager_dir)
    if task:
        append_task(backlog, task)
    elif not backlog.exists():
        backlog.parent.mkdir(parents=True, exist_ok=True)
        write_template(backlog)
    atomic_write_json(path, {**existing, **asdict(configured)})
    print(f"Saved {path}. Required checks: {len(commands)}. Run call limit: {limit}.")
    print("Harbor's local files are excluded through Git's local info/exclude; .gitignore was not changed.")
    print(f"1. Review {task.task_id} in {configured.backlog_file}." if task else "1. Run task-harbor add-task to enter a task and acceptance criteria.")
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
