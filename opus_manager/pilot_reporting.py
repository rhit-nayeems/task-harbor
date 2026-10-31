"""Offline human review and complete-cohort summaries for comparison experiments."""
from __future__ import annotations

import hashlib
import html
import json
import math
import time
import uuid
from pathlib import Path

from .state import atomic_write_json


def trial_id(row):
    if not isinstance(row, dict):
        raise ValueError("Comparison trial must be an object")
    task, repetition, arm = row.get("task"), row.get("repetition"), row.get("arm")
    if not isinstance(task, str) or not task or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in task):
        raise ValueError("Invalid task ID in comparison results")
    if type(repetition) is not int or repetition < 0 or arm not in {"direct", "harbor"}:
        raise ValueError("Invalid repetition or arm in comparison results")
    return f"{task}-{repetition}-{arm}"


def fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, allow_nan=False).encode()).hexdigest()


def load_trials(root):
    path = root / "results.json"
    if not path.exists():
        raise ValueError("No executed comparison results. A prepared schedule is not evaluation evidence.")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Comparison results must be a nonempty list")
    indexed = {}
    for row in rows:
        key = trial_id(row)
        if key in indexed:
            raise ValueError("Duplicate comparison trial: " + key)
        indexed[key] = row
    schedule = root / "schedule.json"
    if not schedule.exists():
        raise ValueError("Saved schedule is required to account for all attempted and unexecuted trials.")
    if schedule.exists():
        planned = json.loads(schedule.read_text(encoding="utf-8"))
        expected = {}
        for task, repetition, arm in planned:
            row = {"task": task, "repetition": repetition, "arm": arm}
            key = trial_id(row)
            if key in expected:
                raise ValueError("Duplicate trial in schedule")
            expected[key] = row
        if set(indexed) - set(expected):
            raise ValueError("Results contain trials outside the saved schedule")
        for key, row in expected.items():
            if key not in indexed:
                indexed[key] = {**row, "missing_result": True}
    return indexed


def record_feedback(args):
    root = args.experiment.resolve()
    rows = load_trials(root)
    if args.trial not in rows or rows[args.trial].get("missing_result"):
        raise ValueError("Choose a trial with a recorded result")
    values = [args.minutes, args.supervision_minutes, args.repair_minutes]
    if any(not math.isfinite(v) or v < 0 for v in values) or not math.isfinite(sum(values)) or args.regressions < 0:
        raise ValueError("Time and regressions must be finite and nonnegative")
    record = {"trial": args.trial, "outcome": args.outcome, "review_minutes": args.minutes,
              "supervision_minutes": args.supervision_minutes, "repair_minutes": args.repair_minutes,
              "active_minutes": sum(values), "regressions": args.regressions, "note": args.note,
              "recorded_ns": time.time_ns(), "result_sha256": fingerprint(rows[args.trial])}
    atomic_write_json(root / "human-feedback" / (uuid.uuid4().hex + ".json"), record)
    print("Feedback saved. The latest assessment replaces earlier totals for this trial; include cumulative effort.")


def comparison_report(root: Path):
    rows = load_trials(root)
    feedback = {}
    stale = 0
    for path in (root / "human-feedback").glob("*.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or not {"trial", "outcome", "active_minutes", "regressions", "recorded_ns", "result_sha256"} <= entry.keys():
            raise ValueError(f"Invalid human feedback: {path.name}")
        if (entry["outcome"] not in {"accepted", "needs_changes", "rejected", "abandoned"}
                or type(entry["active_minutes"]) not in {int, float} or not math.isfinite(entry["active_minutes"]) or entry["active_minutes"] < 0
                or type(entry["regressions"]) is not int or entry["regressions"] < 0 or type(entry["recorded_ns"]) is not int):
            raise ValueError(f"Invalid human feedback values: {path.name}")
        key = entry["trial"]
        if key not in rows or entry["result_sha256"] != fingerprint(rows[key]):
            stale += 1
            continue
        if key not in feedback or entry["recorded_ns"] > feedback[key]["recorded_ns"]:
            feedback[key] = entry
    arms = {}
    for arm in ("direct", "harbor"):
        selected = {k: r for k, r in rows.items() if r["arm"] == arm}
        assessments = [feedback[k] for k in selected if k in feedback]
        accepted = sum(e["outcome"] == "accepted" for e in assessments)
        effort = sum(e["active_minutes"] for e in assessments)
        complete = bool(selected) and len(assessments) == len(selected)
        known_usage = [r["usage"] for r in selected.values() if "usage" in r]
        tokens = {}
        for usage in known_usage:
            for key, value in usage.get("tokens", {}).items():
                tokens[key] = tokens.get(key, 0) + value
        arms[arm] = {"attempts": len(selected), "missing_results": sum(bool(r.get("missing_result")) for r in selected.values()),
            "independently_passing": sum(r.get("accepted") is True for r in selected.values()),
            "execution_errors": sum(bool(r.get("error")) for r in selected.values()),
            "human_reviewed": len(assessments), "human_accepted": accepted,
            "human_outcomes": {outcome: sum(e["outcome"] == outcome for e in assessments)
                               for outcome in ("accepted", "needs_changes", "rejected", "abandoned")},
            "human_effort_complete": complete, "measured_active_minutes": effort,
            "active_minutes_per_accepted_task": effort / accepted if complete and accepted else None,
            "observed_regressions": sum(e["regressions"] for e in assessments),
            "reported_cost_usd": sum(u.get("reported_cost_usd", 0) for u in known_usage),
            "trials_without_usage": len(selected) - len(known_usage),
            "calls_without_cost": sum(u.get("calls_without_cost", 0) for u in known_usage), "reported_tokens": tokens,
            "recorded_elapsed_seconds": sum(r.get("elapsed_seconds", 0) for r in selected.values()),
            "trials_without_elapsed_time": sum("elapsed_seconds" not in r for r in selected.values())}
    return {"experiment": str(root.resolve()), "arms": arms, "stale_feedback_records": stale,
            "trials": [{"id": key, "result": row, "human_feedback": feedback.get(key)} for key, row in rows.items()],
            "notes": ["Human effort includes rejected, abandoned, and failed attempts. Missing feedback is unknown, not zero.",
                      "Minutes per accepted task is withheld until all scheduled attempts in that arm have human feedback.",
                      "Independent checks and human acceptance are separate. Costs and tokens are reported values, not guaranteed totals.",
                      "Regressions are human observations at review time, not a guarantee against later defects.",
                      "No statistical or production-performance claim is inferred from this report."]}


METRICS = ("attempts", "missing_results", "execution_errors", "independently_passing", "human_reviewed", "human_accepted", "human_effort_complete",
           "measured_active_minutes", "active_minutes_per_accepted_task", "observed_regressions",
           "reported_cost_usd", "trials_without_usage", "calls_without_cost", "reported_tokens",
           "recorded_elapsed_seconds", "trials_without_elapsed_time")


def report_text(report):
    lines = ["Task Harbor comparison", "Metric | Direct agent | Task Harbor"]
    for metric in METRICS:
        values = [report["arms"][arm][metric] for arm in ("direct", "harbor")]
        lines.append(metric.replace("_", " ") + " | " + " | ".join("unknown" if v is None else str(v) for v in values))
    lines.extend(report["notes"])
    lines.append(f"Stale feedback ignored: {report['stale_feedback_records']}")
    return "\n".join(lines)


def run_command(args):
    if args.command == "compare-feedback":
        record_feedback(args)
        return 0
    report = comparison_report(args.experiment.resolve())
    if args.html:
        esc = lambda value: html.escape(str(value))
        rows = "".join("<tr><th>" + esc(metric.replace("_", " ")) + "</th>" + "".join(
            "<td>" + esc("unknown" if report["arms"][arm][metric] is None else report["arms"][arm][metric]) + "</td>"
            for arm in ("direct", "harbor")) + "</tr>" for metric in METRICS)
        trials = "".join("<tr><td>" + esc(trial["id"]) + "</td><td>" + esc((trial["human_feedback"] or {}).get("outcome", "not reviewed"))
            + "</td><td>" + esc((trial["human_feedback"] or {}).get("active_minutes", "unknown"))
            + "</td><td>" + esc(trial["result"].get("error") or ("No result recorded" if trial["result"].get("missing_result") else "Recorded"))
            + "</td></tr>" for trial in report["trials"])
        args.html.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Task Harbor comparison</title><style>body{max-width:1100px;margin:2rem auto;padding:1rem;font:16px system-ui;background:#101923;color:#e2eaf2}'
            'table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.8rem;border-bottom:1px solid #35414d;overflow-wrap:anywhere}'
            '.scroll{overflow:auto}li{line-height:1.7;margin:.5rem 0}</style><h1>Comparison results</h1>'
            '<div class="scroll"><table><thead><tr><th>Metric</th><th>Direct agent</th><th>Task Harbor</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
            '<h2>Interpretation</h2><ul>' + "".join("<li>" + esc(note) + "</li>" for note in report["notes"]) + '</ul>'
            f'<p>Stale feedback ignored: {report["stale_feedback_records"]}</p>'
            '<h2>Every scheduled attempt</h2><div class="scroll"><table><thead><tr><th>Trial</th><th>Human outcome</th><th>Active minutes</th><th>Execution</th></tr></thead><tbody>'
            + trials + '</tbody></table></div></html>', encoding="utf-8")
    print(json.dumps(report, indent=2) if args.json else report_text(report))
    return 0
