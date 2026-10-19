from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class GitError(RuntimeError):
    pass


@dataclass
class CmdResult:
    code: int
    stdout: str
    stderr: str


def run(cmd: list[str], cwd: Path, *, check: bool = True, timeout: int = 120, env: dict[str, str] | None = None) -> CmdResult:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    result = CmdResult(proc.returncode, proc.stdout.rstrip(), proc.stderr.rstrip())
    if check and proc.returncode != 0:
        raise GitError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{result.stderr or result.stdout}")
    return result


def git(repo: Path, *args: str, check: bool = True, timeout: int = 120) -> CmdResult:
    return run(["git", *args], repo, check=check, timeout=timeout)


def ensure_repo(repo: Path) -> None:
    if git(repo, "rev-parse", "--is-inside-work-tree", check=False).stdout != "true":
        raise GitError(f"Not a Git worktree: {repo}")


def current_branch(repo: Path) -> str:
    branch = git(repo, "branch", "--show-current").stdout
    if not branch:
        raise GitError("Detached HEAD is not supported for manager initialization. Check out a base branch first.")
    return branch


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").stdout


def status_paths(repo: Path) -> list[str]:
    out = git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.strip('"'))
    return paths


def meaningful_dirty(repo: Path, manager_dir: str, backlog_file: str | None = None) -> list[str]:
    prefix = manager_dir.rstrip("/") + "/"
    ignored = {manager_dir}
    if backlog_file:
        ignored.add(backlog_file.replace("\\", "/"))
    return [
        p for p in status_paths(repo)
        if p.replace("\\", "/") not in ignored and not p.replace("\\", "/").startswith(prefix)
    ]


def ensure_local_exclude(repo: Path, manager_dir: str) -> None:
    git_dir = Path(git(repo, "rev-parse", "--git-path", "info/exclude").stdout)
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    git_dir.parent.mkdir(parents=True, exist_ok=True)
    existing = git_dir.read_text(encoding="utf-8") if git_dir.exists() else ""
    entry = f"/{manager_dir.strip('/')}/"
    if entry not in existing.splitlines():
        with git_dir.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(entry + "\n")


def branch_exists(repo: Path, branch: str) -> bool:
    return git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False).code == 0


def worktree_add(repo: Path, path: Path, branch: str, start_point: str, *, create_branch: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if any(path.iterdir()):
            raise GitError(f"Worktree path already exists and is not empty: {path}")
        path.rmdir()
    if create_branch:
        git(repo, "worktree", "add", "-b", branch, str(path), start_point, timeout=300)
    else:
        git(repo, "worktree", "add", str(path), branch, timeout=300)


def detached_worktree_add(repo: Path, path: Path, commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.rmtree(path)
    git(repo, "worktree", "add", "--detach", str(path), commit, timeout=300)


def worktree_remove(repo: Path, path: Path, *, force: bool = True) -> None:
    if not path.exists():
        return
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    git(repo, *args, check=False, timeout=300)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def changed_paths(repo: Path) -> list[str]:
    return status_paths(repo)


def matches_protected(path: str, protected: Iterable[str], backlog_file: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized == backlog_file.replace("\\", "/"):
        return True
    for pat in protected:
        p = pat.replace("\\", "/")
        if fnmatch.fnmatch(normalized, p) or normalized == p.rstrip("/") or normalized.startswith(p.rstrip("/") + "/"):
            return True
    return False


def restore_paths(repo: Path, paths: Iterable[str]) -> None:
    tracked: list[str] = []
    untracked: list[str] = []
    for p in paths:
        if git(repo, "ls-files", "--error-unmatch", "--", p, check=False).code == 0:
            tracked.append(p)
        else:
            untracked.append(p)
    if tracked:
        git(repo, "restore", "--staged", "--worktree", "--", *tracked, check=False)
    for p in untracked:
        target = repo / p
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink(missing_ok=True)


def checkpoint(repo: Path, message: str) -> str:
    if not changed_paths(repo):
        return head(repo)
    git(repo, "add", "-A")
    # Local checkpoint commits are infrastructure, not final delivery commits.
    result = git(repo, "commit", "-m", message, check=False, timeout=300)
    if result.code != 0:
        text = (result.stderr + "\n" + result.stdout).lower()
        if "nothing to commit" not in text:
            raise GitError(f"Could not create local checkpoint commit: {result.stderr or result.stdout}")
    return head(repo)


def merge_branch(integration_repo: Path, branch: str, task_id: str) -> tuple[bool, str]:
    result = git(
        integration_repo,
        "merge", "--no-ff", "--no-edit", branch,
        check=False,
        timeout=300,
    )
    if result.code == 0:
        return True, head(integration_repo)
    conflict = git(integration_repo, "diff", "--name-only", "--diff-filter=U", check=False).stdout
    git(integration_repo, "merge", "--abort", check=False)
    return False, conflict or result.stderr or result.stdout


def diff_range(repo: Path, base: str, tip: str = "HEAD") -> str:
    return git(repo, "diff", "--stat", f"{base}..{tip}", check=False).stdout + "\n\n" + git(
        repo, "diff", "--find-renames", f"{base}..{tip}", check=False, timeout=300
    ).stdout


def repo_snapshot(repo: Path) -> str:
    branch = git(repo, "branch", "--show-current", check=False).stdout or "DETACHED"
    h = head(repo)
    status = git(repo, "status", "--short", check=False).stdout or "clean"
    recent = git(repo, "log", "-5", "--oneline", check=False).stdout
    return f"branch: {branch}\nhead: {h}\nstatus:\n{status}\nrecent commits:\n{recent}"


def remote_block_env(hooks_dir: Path) -> dict[str, str]:
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-push"
    hook.write_text("#!/bin/sh\necho 'Remote git push blocked by Task Harbor' >&2\nexit 1\n", encoding="utf-8")
    try:
        hook.chmod(0o755)
    except OSError:
        pass
    env = os.environ.copy()
    # Environment-scoped Git config: inherited by git processes spawned by Claude.
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "core.hooksPath"
    env["GIT_CONFIG_VALUE_0"] = str(hooks_dir)
    return env
