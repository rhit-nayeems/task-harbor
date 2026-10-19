# Evaluation

The automated test suite validates the harness using simulated model responses.
It does not measure how well Claude solves real engineering tasks.

`evaluations/run.py` provides a small opt-in live benchmark: three independent
Python tasks covering boundary behavior, normalization, and a numeric bug. An
external grader checks the integrated code, independently of agent QA verdicts.
It saves baseline results, usage, task outcomes, and final grader results.

```powershell
python -m pip install -e .
# Prepare fixtures and prove the starting implementations fail. No model calls.
python evaluations/run.py C:\temp\harbor-fixtures
# A separate run that consumes Claude usage; requires an authenticated CLI.
python evaluations/run.py C:\temp\harbor-live --live
```

Use a new directory each time. Git identity must already be configured. Live runs
have a 40-call ceiling and a $10 estimated run budget, with a $2 estimated call
cap; dollar caps can overshoot within a model request. No benchmark result from a
live model is claimed for this release. The smoke benchmark is deliberately small
and is not evidence of performance on production repositories.

For realistic evaluation, add versioned fixtures from repositories you own and
hold back regression checks from the managed source tree. Include dependency
changes, multi-file features, merge conflicts, unavailable infrastructure, and
interruptions during repair and review. Run several repetitions of each case.

Compare independently verified completion, regression failures, reported tokens,
estimated cost, elapsed time, and operator interventions. Record model/CLI
versions and configuration with each experiment. Compare deterministic versus
model scheduling and optional final review on the same fixtures. Do not call an
unverified or budget-stopped task successful, and do not treat missing cost as
zero. The offline JSON report exposes the base metrics for further analysis.
