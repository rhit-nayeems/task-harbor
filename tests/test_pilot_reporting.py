import json

from opus_manager.cli import main
from opus_manager.pilot_reporting import comparison_report
from opus_manager.state import atomic_write_json


def experiment(root):
    rows = [{"task": "T", "repetition": rep, "arm": arm, "accepted": rep == 0,
             "usage": {"reported_cost_usd": 0, "calls_without_cost": 1, "tokens": {"input_tokens": 40}},
             "elapsed_seconds": 3} for rep in range(2) for arm in ("direct", "harbor")]
    atomic_write_json(root / "results.json", rows)
    atomic_write_json(root / "schedule.json", [[r["task"], r["repetition"], r["arm"]] for r in rows])
    return rows


def feedback(root, trial, outcome="accepted", minutes="2"):
    return main(["compare-feedback", "--experiment", str(root), "--trial", trial,
                 "--outcome", outcome, "--minutes", minutes, "--supervision-minutes", "0",
                 "--repair-minutes", "0", "--regressions", "0"])


def test_complete_cohort_includes_failed_effort_and_latest_feedback(tmp_path):
    experiment(tmp_path)
    assert feedback(tmp_path, "T-0-direct") == 0
    assert feedback(tmp_path, "T-1-direct", "abandoned", "8") == 0
    assert feedback(tmp_path, "T-0-harbor", minutes="5") == 0
    report = comparison_report(tmp_path)
    assert report["arms"]["direct"]["active_minutes_per_accepted_task"] == 10
    assert report["arms"]["harbor"]["active_minutes_per_accepted_task"] is None
    assert feedback(tmp_path, "T-1-harbor", minutes="5") == 0
    assert feedback(tmp_path, "T-0-harbor", minutes="3") == 0
    report = comparison_report(tmp_path)
    assert report["arms"]["harbor"]["active_minutes_per_accepted_task"] == 4
    assert report["arms"]["harbor"]["human_accepted"] == 2
    assert report["arms"]["harbor"]["independently_passing"] == 1
    assert report["arms"]["harbor"]["calls_without_cost"] == 2
    output = tmp_path / "report.html"
    assert main(["compare-report", "--experiment", str(tmp_path), "--html", str(output)]) == 0
    assert "Direct agent" in output.read_text()


def test_missing_trials_stale_feedback_and_invalid_times_are_not_counted(tmp_path):
    rows = experiment(tmp_path)
    assert feedback(tmp_path, "T-0-direct", minutes="nan") == 2
    assert feedback(tmp_path, "T-0-direct", minutes="-1") == 2
    assert feedback(tmp_path, "T-0-direct") == 0
    rows[0]["accepted"] = False
    atomic_write_json(tmp_path / "results.json", rows[:-1])
    report = comparison_report(tmp_path)
    assert report["stale_feedback_records"] == 1
    assert report["arms"]["direct"]["human_reviewed"] == 0
    assert report["arms"]["harbor"]["missing_results"] == 1
    assert feedback(tmp_path, "T-1-harbor") == 2
    assert report["arms"]["harbor"]["active_minutes_per_accepted_task"] is None


def test_preparation_and_duplicate_results_cannot_be_reported_as_evidence(tmp_path):
    assert main(["compare-report", "--experiment", str(tmp_path)]) == 2
    rows = experiment(tmp_path)
    atomic_write_json(tmp_path / "results.json", rows + rows[:1])
    assert main(["compare-report", "--experiment", str(tmp_path)]) == 2
    atomic_write_json(tmp_path / "results.json", rows)
    (tmp_path / "schedule.json").unlink()
    assert main(["compare-report", "--experiment", str(tmp_path)]) == 2
