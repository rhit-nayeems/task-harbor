"""Offline run reports: no server, external assets, or model calls."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .state import load_state
from .usage import summarize


def task_evidence(run_dir: Path, task) -> dict:
    if not task.last_qa_path:
        return {"verification_level": "not_verified"}
    path = Path(task.last_qa_path).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.exists():
        return {"verification_level": "evidence_unavailable"}
    return json.loads(path.read_text(encoding="utf-8"))


def review_summary(task: dict, feedback: list) -> list[str]:
    """Describe recorded evidence without treating model claims as independent proof."""
    evidence = task["evidence"]
    files = evidence.get("changes", {}).get("files", [])
    checks = evidence.get("harness_checks", [])
    passed = sum(c.get("exit_code") == 0 and not c.get("timed_out") for c in checks)
    checkpoint = evidence.get("checkpoint_commit")
    matching = bool(checkpoint and checkpoint == task.get("checkpoint"))
    lines = ["Changed files: " + (", ".join(f["path"] for f in files) or "No diff evidence recorded."),
             f"Checks: {passed} passed, {len(checks) - passed} failed/timed out, {len(checks)} recorded.",
             "Checkpoint evidence: " + ("matches the task checkpoint." if matching else "missing or does not match; verify before accepting.")]
    if evidence.get("summary"):
        lines.append("Recorded QA summary: " + str(evidence["summary"]))
    acceptance = evidence.get("acceptance", [])
    for index, criterion in enumerate(task.get("acceptance_criteria", []), 1):
        item = next((a for a in acceptance if a.get("criterion_id") == f"AC-{index}" or a.get("criterion") == criterion), {})
        lines.append(f"AC-{index}: {criterion}; recorded {item.get('status', 'NOT VERIFIED')}"
                     + (f"; evidence: {item['evidence']}" if item.get("evidence") else "; no supporting evidence recorded."))
    warnings = [f"{f['path']}: {flag}" for f in files for flag in f.get("warnings", [])]
    if not checks:
        lines.append("Needs attention: no executed checks recorded.")
    for warning in warnings:
        lines.append("Needs attention: " + warning)
    for risk in evidence.get("risks", []):
        lines.append("Needs attention: " + str(risk))
    reviews = [f for f in feedback if f.get("task") == task["id"] and f.get("checkpoint") == task.get("checkpoint") and task.get("checkpoint")]
    lines.append("Human review: " + (reviews[-1]["outcome"] + " for this checkpoint." if reviews else "pending for this checkpoint."))
    if reviews:
        total = reviews[-1].get("active_engineer_minutes")
        lines.append("Recorded engineer time (latest feedback): " + (f"{total:g} minutes." if total is not None
                     else "incomplete; include supervision and repair minutes as well as review."))
    lines.append("Next: inspect the diff and acceptance evidence, then record feedback. Passing checks do not prove correctness.")
    return lines


def review_text(report: dict, task_id: str | None = None) -> str:
    lines = [f'Task Harbor review: {report["run_id"]}', f'Branch: {report["integration_branch"]}']
    selected = [t for t in report["tasks"] if task_id is None or t["id"] == task_id]
    if not selected:
        raise ValueError(f"Task not found: {task_id}")
    for task in selected:
        evidence = task["evidence"]
        lines += ["", f'{task["id"]}: {task["title"]}', f'Status: {task["status"]}',
                  *review_summary(task, report.get("feedback", [])),
                  f'Checkpoint: {evidence.get("checkpoint_commit", "not recorded")}',
                  f'Verification: {evidence.get("verification_level", "legacy/unknown")}',
                  "Task agreement: " + json.dumps(task["contract"], indent=2),
                  "Acceptance: " + json.dumps(evidence.get("acceptance", []), indent=2),
                  "Executed checks: " + json.dumps(evidence.get("harness_checks", []), indent=2),
                  "Before/after reproduction: " + json.dumps(evidence.get("reproduction", {}), indent=2),
                  "Artifacts: " + json.dumps(evidence.get("artifacts", []), indent=2),
                  "Failure classification: " + json.dumps(evidence.get("failure_classification", []), indent=2),
                  "Human feedback: " + json.dumps([f for f in report.get("feedback", []) if f.get("task") == task["id"]], indent=2),
                  "Unverified / risks: " + json.dumps(evidence.get("risks", []))]
        for file in evidence.get("changes", {}).get("files", []):
            lines += [f'\nFILE: {file["path"]}', "Review flags: " + ", ".join(file["warnings"]), file["diff"]]
    return "\n".join(lines)


def run_report(run_dir: Path) -> dict:
    state = load_state(run_dir / "state.json")
    usage_file = run_dir / "usage.json"
    usage = json.loads(usage_file.read_text(encoding="utf-8")) if usage_file.exists() else {"calls": []}
    feedback_path = run_dir / "feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.exists() else []
    completed = sum(t.status.value == "COMPLETE" for t in state.tasks.values())
    totals = summarize(usage)
    return {"run_id": state.run_id, "provider": state.provider, "integration_branch": state.integration_branch,
            "feedback": feedback, "active_review_minutes": sum(f["active_review_minutes"] for f in feedback),
            "paused": state.paused, "stop_reason": state.stop_reason,
            "completed": completed, "total": len(state.tasks), "usage": totals,
            "reported_cost_per_completed_task": totals["reported_cost_usd"] / completed if completed else None,
            "tasks": [{"id": t.task_id, "title": t.title, "status": t.status.value,
                       "dependencies": t.dependencies, "blocked_reason": t.blocked_reason,
                       "next_action": t.next_action, "generation": t.generation,
                       "checkpoint": t.checkpoint_commit,
                       "acceptance_criteria": t.acceptance_criteria,
                       "contract": t.metadata.get("contract", {}),
                       "evidence": task_evidence(run_dir, t),
                       "usage": summarize({"calls": [c for c in usage["calls"] if c.get("task") == t.task_id]})}
                      for t in state.tasks.values()]}


def write_html(report: dict, output: Path) -> None:
    esc = lambda value: html.escape(str(value if value is not None else "—"))
    rows = "".join("<tr>" + "".join(f"<td>{esc(t[k])}</td>" for k in
                   ("id", "title", "status", "blocked_reason", "next_action")) + "</tr>" for t in report["tasks"])
    details = "".join(f'<details><summary>{esc(t["id"])}: {esc(t["title"])}</summary><pre>{esc(review_text(report, t["id"]))}</pre></details>' for t in report["tasks"])
    summaries = "".join(f'<section><h3>{esc(t["id"])}: {esc(t["title"])}</h3><ul>' +
                        "".join(f"<li>{esc(line)}</li>" for line in review_summary(t, report.get("feedback", []))) +
                        "</ul></section>" for t in report["tasks"])
    output.write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Task Harbor · Run report</title>
<style>body{{font:16px system-ui;margin:3rem;background:#101923;color:#e2eaf2}}h1{{color:#68debf}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:1rem;text-align:left;border-bottom:1px solid #35414d}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.scroll{{overflow:auto}}p,li{{line-height:1.7}}body{{max-width:1100px;margin:2rem auto;padding:0 1rem}}section{{border:1px solid #35414d;padding:1rem;margin:1rem 0}}li{{overflow-wrap:anywhere}}</style>
<h1>Task Harbor</h1><p>Run {esc(report["run_id"])} · {report["completed"]}/{report["total"]} complete</p>
<p>{esc(report["integration_branch"])}<br>{esc(report["stop_reason"])}</p>
<h2>Review summary</h2>{summaries}
<h2>Usage</h2><pre>{esc(json.dumps(report["usage"], indent=2))}</pre>
<p>Costs are CLI estimates. Calls without reported cost are unknown, not free. Snapshot; regenerate to refresh.</p>
<div class="scroll"><table><thead><tr><th>Task</th><th>Title</th><th>Status</th><th>Blocked</th><th>Next action</th></tr></thead>
<tbody>{rows}</tbody></table></div><h2>Evidence and diffs</h2>{details}</html>''', encoding="utf-8")
