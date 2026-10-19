"""Deterministic environment recipes and baseline evidence in disposable worktrees."""
from __future__ import annotations

import json
import os
import shutil
import uuid
import hashlib
from pathlib import Path

from .gitops import detached_worktree_add, worktree_remove, changed_paths, git
from .verification import run_checks


def verification_mutations(cfg, cwd: Path) -> list[str]:
    tracked = set(filter(None, git(cwd, "ls-files", "-z").stdout.split("\0")))
    return [p for p in changed_paths(cwd) if p in tracked or p not in cfg.verification_artifacts]


def collect_artifacts(cfg, cwd: Path, destination: Path) -> list[dict]:
    """Retain explicit check outputs; never follow links outside the worktree."""
    records = []
    for name in cfg.verification_artifacts:
        source = cwd / name
        record = {"source": name}
        if not source.resolve().is_relative_to(cwd.resolve()) or source.is_symlink():
            record["status"] = "rejected_path"
        elif not source.is_file():
            record["status"] = "missing"
        elif source.stat().st_size > 20 * 1024 * 1024:
            record["status"] = "too_large"
        else:
            data = source.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / (digest + source.suffix)
            target.write_bytes(data)
            record.update(status="retained", path=str(target.resolve()), sha256=digest, bytes=len(data))
        records.append(record)
    return records


def suggestions(repo: Path) -> list[str]:
    found = []
    package = repo / "package.json"
    if package.exists():
        scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        for name in ("test", "lint", "build"):
            if name in scripts:
                found.append(f"npm run {name}")
    if (repo / "pytest.ini").exists() or ((repo / "pyproject.toml").exists() and (repo / "tests").is_dir()):
        found.append("python -m pytest")
    if (repo / "Cargo.toml").exists():
        found.append("cargo test")
    if (repo / "go.mod").exists():
        found.append("go test ./...")
    return found


def execute_checks(cfg, cwd: Path, env=None) -> dict:
    missing = [f"executable:{name}" for name in cfg.required_executables if not shutil.which(name)]
    missing += [f"environment:{name}" for name in cfg.required_env if not (env or os.environ).get(name)]
    setup = []
    checks = []
    if not missing:
        setup = run_checks(cfg.setup_commands, cwd, timeout=cfg.verification_timeout_seconds,
                           limit=cfg.evidence_max_chars, env=env)
        if all(c["exit_code"] == 0 and not c["timed_out"] for c in setup):
            checks = run_checks(cfg.verification_commands, cwd, timeout=cfg.verification_timeout_seconds,
                                limit=cfg.evidence_max_chars, env=env)
    # Explicit artifact paths may be newly generated, never edits to tracked files.
    mutation = verification_mutations(cfg, cwd)
    status = "PASS"
    if missing or any(c["exit_code"] or c["timed_out"] for c in setup) or mutation:
        status = "ENVIRONMENT_BLOCKED"
    elif any(c["exit_code"] or c["timed_out"] for c in checks):
        status = "FAIL"
    elif not checks:
        status = "UNVERIFIED"
    return {"status": status, "missing": missing, "setup": setup, "checks": checks,
            "mutated_paths": mutation, "commands": list(cfg.verification_commands)}


def baseline(repo: Path, cfg, commit: str, env=None) -> dict:
    path = repo.parent / f".{repo.name}-harbor-preflight-{uuid.uuid4().hex}"
    detached_worktree_add(repo, path, commit)
    try:
        result = execute_checks(cfg, path, env)
        result.update(commit=commit, suggestions=suggestions(path))
        return result
    finally:
        worktree_remove(repo, path, force=True)
