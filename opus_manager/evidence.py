"""Review inputs and human-readable evidence without model-generated claims."""
from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path

from .gitops import git


def change_evidence(repo: Path, base: str, tip: str, cfg, contract=None) -> dict:
    contract = contract or {}
    names = git(repo, "diff", "--no-renames", "--name-only", "-z", base, tip).stdout.split("\0")
    files = []
    for name in filter(None, names):
        if name == cfg.backlog_file or name == cfg.manager_dir or name.startswith(cfg.manager_dir + "/"):
            continue
        patch = git(repo, "diff", "--no-ext-diff", "--no-renames", base, tip, "--", name, timeout=300).stdout
        warnings = []
        allowed = contract.get("allowed_paths", [])
        if allowed and not any(fnmatch.fnmatchcase(name, pattern) for pattern in allowed):
            warnings.append("outside_declared_scope")
        if any(line.startswith("-") and not line.startswith("---") and ("assert" in line or "expect(" in line) for line in patch.splitlines()):
            warnings.append("removed_assertion_review_required")
        if any(line.startswith("+") and any(token in line for token in (".skip(", "@pytest.mark.skip", "@unittest.skip")) for line in patch.splitlines()):
            warnings.append("skipped_test_review_required")
        if name.rsplit("/", 1)[-1] in {"package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod"}:
            warnings.append("dependency_or_build_change")
        files.append({"path": name, "diff": patch, "warnings": warnings,
                      "sha256": hashlib.sha256(patch.encode()).hexdigest()})
    return {"base_commit": base, "checkpoint_commit": tip, "files": files}


def review_chunks(evidence: dict, limit: int):
    for file in evidence["files"]:
        patch = file["diff"]
        count = max(1, (len(patch) + limit - 1) // limit)
        for index in range(count):
            yield {"path": file["path"], "part": index + 1, "parts": count,
                   "diff": patch[index * limit:(index + 1) * limit], "sha256": file["sha256"]}


def failure_signature(result: dict) -> str:
    # Ignore timestamps, runtime, outputs and model prose; unchanged tree is also
    # required by the caller, so a productive repair is not stopped by this signal.
    payload = {"verdict": result.get("verdict"),
               "checks": [(c.get("command"), c.get("exit_code"), c.get("timed_out")) for c in result.get("harness_checks", [])],
               "acceptance": [(c.get("criterion_id"), c.get("status")) for c in result.get("acceptance", [])]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
