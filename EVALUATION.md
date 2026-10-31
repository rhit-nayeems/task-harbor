# Evaluation

The automated test suite validates the harness using simulated model responses.
It does not measure how well a model solves real engineering tasks.

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

For GPT, use `--provider codex --model gpt-6.1-sol --live` with an available
model and authenticated Codex CLI. GPT runs retain the call ceiling but have no
dollar cap; the Codex CLI does not expose the required cost-budget control.

## Compare a direct agent with Task Harbor

`task-harbor compare` runs each task in two fresh clones at a pinned source commit.
Both arms use the same configured provider, model, effort, task, and environment
recipe. The direct arm is one agent invocation with its normal tool loop. Harbor
uses its configured workflow. Ordering is shuffled with a fixed seed.

Create `comparison.json` next to your project, replacing the repository path and
commit. Use a model available to your account:

```json
{
  "repo": "./my-project",
  "commit": "REPLACE_WITH_COMMIT_SHA",
  "config": {
    "provider": "codex",
    "model": "REPLACE_WITH_AVAILABLE_MODEL",
    "verification_commands": ["python -m pytest tests"],
    "max_agent_calls": 40
  },
  "tasks": [{
    "id": "SEARCH-1",
    "title": "Handle empty search queries",
    "acceptance_criteria": ["An empty query returns an empty result list"],
    "grader_commands": ["python /absolute/path/to/independent_grader.py"]
  }]
}
```

```sh
task-harbor compare --manifest comparison.json --output prepared
task-harbor compare --manifest comparison.json --output experiment --repetitions 3 --live
```

Preparation validates and saves the manifest and schedule without invoking agents
or graders. Live execution consumes provider usage and runs your shell commands.
Use a new output directory each time. The repository needs a configured Git author.
Task agreements can be included under each task's `contract` field.

Every trial retains its checkout and `result.json`. Aggregate `results.json` and
`summary.json` include unsuccessful trials. Results record command outcomes,
usage, elapsed time, provider CLI version, configuration, and source commit.
The legacy `accepted` field means all independent grader commands passed; it is
not a human acceptance decision. Human outcome and active time remain null until
you collect that evidence separately. Normal Harbor runs support `feedback` for
recording review time and acceptance.

The grader is omitted from model prompts, but agents are not isolated from host
files. This is not an adversarial benchmark sandbox. Keep graders outside the
managed source tree, inspect outputs, and ensure they actually detect regressions.
The benchmark does not enforce equal total tokens or agent turns between arms;
report the recorded cost and effort alongside completion. A Harbor run that pauses
is still graded on its integrated result, with the stop reason retained. Provider
costs can be unavailable and must not be treated as free.

## Record human outcomes and compare effort

After reviewing a trial's checkout and independent checks, record the outcome:

```sh
task-harbor compare-feedback --experiment experiment --trial SEARCH-1-0-direct --outcome accepted --minutes 4 --supervision-minutes 3 --repair-minutes 0 --regressions 0
task-harbor compare-report --experiment experiment
task-harbor compare-report --experiment experiment --html comparison.html
task-harbor compare-report --experiment experiment --json
```

Trial IDs are the directory names produced by the comparison runner. Outcomes
include `accepted`, `needs_changes`, `rejected`, and `abandoned`. Time fields
must be explicit: zero means measured zero, not unknown. Include all active
preparation/guidance, review, and repair effort without overlapping categories.
Use `--note` to retain review context. No provider or grader runs in these commands.

Feedback is saved separately from machine results. A new assessment replaces
the previous totals for that trial in the summary; enter cumulative effort,
not just time since the previous assessment. Earlier records remain available.
Feedback is bound to the result record's digest, not an independent proof of
the checkout's contents. Review before changing a checkout; if it changes,
reassess it rather than treating earlier acceptance as current. Feedback for
changed result records is ignored and counted as stale.

The report separates human acceptance from independent check outcomes. It
includes failed and abandoned attempts in effort and keeps scheduled attempts
that lack results visible. Minutes per accepted task is withheld until every
scheduled attempt in that arm has human feedback. If no tasks were accepted,
the value is undefined. Measured subset totals remain labeled as such. Missing
usage stays visible through missing-trial and missing-cost counts. The report
does not infer statistical significance, retention, or commercial value.

No live comparison results are included in this release. The automated tests use
fake providers and real temporary Git repositories to check the experiment
machinery. To establish product value, use representative tasks, repeated trials,
and human review records, then measure whether users return voluntarily.
