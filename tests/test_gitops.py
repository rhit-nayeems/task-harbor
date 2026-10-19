import subprocess
from pathlib import Path

from opus_manager.gitops import (
    checkpoint,
    changed_paths,
    meaningful_dirty,
    worktree_add,
    worktree_remove,
)


def init_repo(path: Path):
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_worktree_isolation_and_checkpoint(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo(repo)
    wt = tmp_path / "wt"
    worktree_add(repo, wt, "task/x", "main")
    (wt / "a.txt").write_text("changed\n")
    assert changed_paths(wt) == ["a.txt"]
    commit = checkpoint(wt, "checkpoint")
    assert commit
    assert (repo / "a.txt").read_text() == "a\n"
    worktree_remove(repo, wt)


def test_meaningful_dirty_ignores_manager_and_backlog(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / ".manager").mkdir()
    (repo / ".manager" / "state.json").write_text("{}")
    (repo / "BACKLOG.md").write_text("board")
    assert meaningful_dirty(repo, ".manager", "BACKLOG.md") == []
    (repo / "a.txt").write_text("dirty")
    assert meaningful_dirty(repo, ".manager", "BACKLOG.md") == ["a.txt"]
