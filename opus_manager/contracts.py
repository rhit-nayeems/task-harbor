"""Operator-owned task intent and checks. Agents cannot authorize new shell commands."""
from __future__ import annotations

import json
from pathlib import Path


def validate_contract(value: dict, criteria_count: int | None = None) -> dict:
    allowed = {"risk", "out_of_scope", "constraints", "allowed_paths", "questions", "answers", "acceptance_checks", "reproduction_commands"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Unknown contract fields")
    if value.get("risk", "normal") not in {"low", "normal", "high"}:
        raise ValueError("Contract risk must be low, normal, or high")
    for key in ("out_of_scope", "constraints", "allowed_paths", "reproduction_commands"):
        items = value.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
            raise ValueError(f"Contract {key} must be a list of nonempty strings")
    for key in ("questions", "answers"):
        items = value.get(key, {})
        if not isinstance(items, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v.strip() for k, v in items.items()):
            raise ValueError(f"Contract {key} must map IDs to nonempty text")
    if set(value.get("answers", {})) - set(value.get("questions", {})):
        raise ValueError("Answers must refer to known question IDs")
    checks = value.get("acceptance_checks", {})
    if not isinstance(checks, dict):
        raise ValueError("acceptance_checks must map AC IDs to command lists")
    for key, commands in checks.items():
        if not isinstance(key, str) or not key.startswith("AC-") or not key[3:].isdigit() or int(key[3:]) < 1:
            raise ValueError("Invalid acceptance ID")
        if criteria_count is not None and int(key[3:]) > criteria_count:
            raise ValueError(f"Unknown acceptance ID: {key}")
        if not isinstance(commands, list) or not commands or any(not isinstance(c, str) or not c.strip() for c in commands):
            raise ValueError("Acceptance commands must be nonempty string lists")
    return value


def load_contracts(repo: Path, manager_dir: str) -> dict:
    path = repo / manager_dir / "contracts.json"
    if not path.exists():
        return {}
    contracts = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(contracts, dict):
        raise ValueError("contracts.json must map task IDs to contracts")
    return {key: validate_contract(value) for key, value in contracts.items()}


def unanswered(contract: dict) -> dict:
    return {key: question for key, question in contract.get("questions", {}).items()
            if not contract.get("answers", {}).get(key)}


def fast_path(task, cfg) -> bool:
    contract = task.metadata.get("contract", {})
    expected = {f"AC-{i+1}" for i in range(len(task.acceptance_criteria))}
    return bool(cfg.workflow == "adaptive" and contract.get("risk") == "low"
                and contract.get("allowed_paths") and expected
                and expected == set(contract.get("acceptance_checks", {}))
                and not unanswered(contract))
