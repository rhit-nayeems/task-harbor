"""Offline run reports: no server, external assets, or model calls."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .state import load_state
from .usage import summarize


def run_report(run_dir: Path) -> dict:
    state = load_state(run_dir / "state.json")
    usage_file = run_dir / "usage.json"
    usage = json.loads(usage_file.read_text(encoding="utf-8")) if usage_file.exists() else {"calls": []}
    completed = sum(t.status.value == "COMPLETE" for t in state.tasks.values())
    totals = summarize(usage)
    return {"run_id": state.run_id, "provider": state.provider, "integration_branch": state.integration_branch,
            "paused": state.paused, "stop_reason": state.stop_reason,
            "completed": completed, "total": len(state.tasks), "usage": totals,
            "reported_cost_per_completed_task": totals["reported_cost_usd"] / completed if completed else None,
            "tasks": [{"id": t.task_id, "title": t.title, "status": t.status.value,
                       "dependencies": t.dependencies, "blocked_reason": t.blocked_reason,
                       "next_action": t.next_action, "generation": t.generation,
                       "checkpoint": t.checkpoint_commit,
                       "usage": summarize({"calls": [c for c in usage["calls"] if c.get("task") == t.task_id]})}
                      for t in state.tasks.values()]}


def write_html(report: dict, output: Path) -> None:
    esc = lambda value: html.escape(str(value if value is not None else "—"))
    rows = "".join("<tr>" + "".join(f"<td>{esc(t[k])}</td>" for k in
                   ("id", "title", "status", "blocked_reason", "next_action")) + "</tr>" for t in report["tasks"])
    output.write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Task Harbor · Run report</title>
<style>body{{font:16px system-ui;margin:3rem;background:#101923;color:#e2eaf2}}h1{{color:#68debf}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:1rem;text-align:left;border-bottom:1px solid #35414d}}
pre{{white-space:pre-wrap}}.scroll{{overflow:auto}}p{{line-height:1.7}}</style>
<h1>Task Harbor</h1><p>Run {esc(report["run_id"])} · {report["completed"]}/{report["total"]} complete</p>
<p>{esc(report["integration_branch"])}<br>{esc(report["stop_reason"])}</p>
<h2>Usage</h2><pre>{esc(json.dumps(report["usage"], indent=2))}</pre>
<p>Costs are CLI estimates. Calls without reported cost are unknown, not free. Snapshot; regenerate to refresh.</p>
<div class="scroll"><table><thead><tr><th>Task</th><th>Title</th><th>Status</th><th>Blocked</th><th>Next action</th></tr></thead>
<tbody>{rows}</tbody></table></div></html>''', encoding="utf-8")
