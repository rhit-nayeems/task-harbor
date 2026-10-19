"""Opt-in, paid smoke benchmark with assertions outside the managed worktree."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from opus_manager.backlog import render_backlog
from opus_manager.config import Config
from opus_manager.models import BacklogTask
from opus_manager.orchestrator import Orchestrator
from opus_manager.reporting import run_report


CHECKS = {
    "clamp": "assert m.clamp(-2, 0, 5) == 0; assert m.clamp(8, 0, 5) == 5; assert m.clamp(3, 0, 5) == 3",
    "slug": "assert m.slug(' Hello, WORLD! ') == 'hello-world'; assert m.slug('a---b') == 'a-b'; assert m.slug('!!!') == ''",
    "mean": "assert m.mean([1, 2]) == 1.5; assert m.mean([-2, 2]) == 0; assert m.mean([]) is None",
}


def grade(worktree: Path) -> dict:
    results = {}
    for name, assertions in CHECKS.items():
        code = "import importlib.util; s=importlib.util.spec_from_file_location('candidate', 'helpers.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); " + assertions
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", code], cwd=worktree,
                                  capture_output=True, text=True, timeout=10)
            results[name] = {"pass": proc.returncode == 0, "error": proc.stderr[-2000:]}
        except subprocess.TimeoutExpired:
            results[name] = {"pass": False, "error": "Timed out"}
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="New benchmark directory; must not exist")
    parser.add_argument("--live", action="store_true", help="Actually invoke the selected provider (consumes usage)")
    parser.add_argument("--provider", choices=["claude", "codex"], default="claude")
    parser.add_argument("--model", help="Explicit model identifier; required for Codex")
    args = parser.parse_args()
    if args.provider == "codex" and not args.model:
        parser.error("--model is required with --provider codex")
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=False)
    repo = root / "repo"
    repo.mkdir()
    (repo / "helpers.py").write_text("def clamp(value, low, high):\n    return value\n\ndef slug(text):\n    return text\n\ndef mean(values):\n    return sum(values) // len(values)\n", encoding="utf-8")
    tasks = {
        "CLAMP": BacklogTask("CLAMP", "Fix numeric clamping in helpers.py", acceptance_criteria=["clamp returns low below the lower bound, high above the upper bound, and the input otherwise"]),
        "SLUG": BacklogTask("SLUG", "Implement an ASCII slug helper", acceptance_criteria=["slug lowercases text, replaces runs of non-ASCII-alphanumeric characters with a hyphen and strips leading/trailing hyphens"]),
        "MEAN": BacklogTask("MEAN", "Fix fractional and empty means", acceptance_criteria=["mean returns the arithmetic mean without integer truncation and returns None for an empty list"]),
    }
    render_backlog(repo / "BACKLOG.md", tasks)
    for command in (["git", "init", "-b", "main"], ["git", "add", "."], ["git", "commit", "-m", "Seed benchmark tasks"]):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
    (root / "baseline.json").write_text(json.dumps(grade(repo), indent=2), encoding="utf-8")
    if not args.live:
        print(f"Prepared fixtures at {repo}. No model calls made. Use a new directory with --live for a paid run.")
        return 0
    cfg = Config(provider=args.provider, model=args.model or "opus",
                 max_agent_calls=40, max_task_agent_calls=12,
                 max_run_cost_usd=10 if args.provider == "claude" else None,
                 max_call_cost_usd=2 if args.provider == "claude" else None,
                 final_code_review=True)
    manager = Orchestrator.start(repo, cfg)
    manager.run()
    report = run_report(manager.paths.run_dir)
    report["independent_checks"] = grade(Path(manager.state.integration_worktree))
    (root / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Results: {root / 'results.json'}")
    return 0 if all(r["pass"] for r in report["independent_checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
