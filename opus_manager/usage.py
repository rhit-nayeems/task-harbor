"""Durable call reservations. Unknown interrupted costs remain reserved on resume."""
from __future__ import annotations

import json
import math
import threading
import time
import uuid
from pathlib import Path

from .config import Config
from .state import atomic_write_json


class RunStopped(RuntimeError):
    pass


class UsageLedger:
    def __init__(self, path: Path, config: Config):
        self.path, self.config = path, config
        self.lock = threading.Lock()

    def read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"calls": []}

    def reserve(self, role: str, task: str | None) -> tuple[str, float | None]:
        with self.lock:
            control = self.path.parent / "stop-request.json"
            if control.exists():
                raise RunStopped("Operator requested a stop; resume explicitly to continue")
            data = self.read()
            calls = data["calls"]
            cfg = self.config
            if cfg.max_agent_calls is not None and len(calls) >= cfg.max_agent_calls:
                raise RunStopped("Agent call budget exhausted")
            if task and cfg.max_task_agent_calls is not None and sum(c.get("task") == task for c in calls) >= cfg.max_task_agent_calls:
                raise RunStopped(f"Task {task} agent call budget exhausted")
            cap = cfg.max_call_cost_usd
            if cfg.max_run_cost_usd is not None:
                spent = sum(c.get("cost_usd") if c.get("cost_usd") is not None else c.get("reserved_usd", 0) or 0 for c in calls)
                # Missing usage from an older/unbudgeted invocation cannot be assumed free.
                if any(c.get("cost_usd") is None and not c.get("reserved_usd") for c in calls):
                    raise RunStopped("Unknown prior cost prevents enforcing the run budget")
                remaining = cfg.max_run_cost_usd - spent
                if remaining < 0.01:
                    raise RunStopped("Estimated run cost budget exhausted (including outstanding reservations)")
                cap = min(cap or remaining / cfg.max_active_planners, remaining)
            call_id = uuid.uuid4().hex
            calls.append({"id": call_id, "role": role, "task": task, "status": "pending",
                          "started_at": time.time(), "reserved_usd": cap, "cost_usd": None})
            atomic_write_json(self.path, data)
            return call_id, cap

    def finish(self, call_id: str, raw: dict | None, error: str | None = None) -> None:
        with self.lock:
            data = self.read()
            call = next(c for c in data["calls"] if c["id"] == call_id)
            raw = raw or {}
            cost = raw.get("total_cost_usd")
            if type(cost) in {int, float} and math.isfinite(cost) and cost >= 0:
                call["cost_usd"] = cost
            call.update(status="failed" if error else "completed", finished_at=time.time(),
                        usage=raw.get("usage", {}), session_id=raw.get("session_id"), error=error)
            atomic_write_json(self.path, data)


def summarize(data: dict) -> dict:
    calls = data.get("calls", [])
    known = [c["cost_usd"] for c in calls if c.get("cost_usd") is not None]
    tokens = {}
    for call in calls:
        for key, value in call.get("usage", {}).items():
            if key.endswith("tokens") and type(value) is int:
                tokens[key] = tokens.get(key, 0) + value
    return {"agent_calls": len(calls), "reported_cost_usd": sum(known),
            "calls_without_cost": len(calls) - len(known), "tokens": tokens}
