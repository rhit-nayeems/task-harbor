# Checks, agreements, and evidence

Start with `task-harbor preflight`. It suggests commands from project files but
runs nothing. Put the commands you trust in `.manager/config.json`, then run
`task-harbor preflight --run-checks`:

```json
{
  "setup_commands": ["python -m pip install -e ."],
  "verification_commands": ["python -m pytest"],
  "required_executables": ["python"],
  "required_env": [],
  "require_verification": true,
  "verification_artifacts": [],
  "workflow": "standard",
  "repeated_failure_limit": 4
}
```

Merge these fields into your existing config. Setup and checks run in disposable
Git worktrees, with the same host tools and environment. They are shell commands,
not sandboxed programs. Setup can change your installed environment; use an
isolated Python environment where appropriate. Environment variable values are
not printed by the preflight validator, but command output can contain secrets.

Each run saves a baseline before calling a model. Missing tools, missing required
environment variables, failed setup, and unexpected Git changes pause the run.
With `require_verification: true`, baseline checks must pass. Leave it false when
working on a known failing baseline; failures are still recorded and candidate
checks must pass. Its default is false for compatibility with existing projects.

Candidate checks run at the task's exact checkpoint before model QA. Failed
checks cannot be overridden by a model PASS, including during review fixes.
Failures that also occur on the baseline are labeled; this is a comparison of
command exit status, not proof that the underlying cause is identical.

## Agree on scope before implementation

Save an agreement as `agreement.json`, then import it for a future run:

```json
{
  "risk": "low",
  "allowed_paths": ["src/search.py", "tests/test_search.py"],
  "out_of_scope": ["Changing the public API"],
  "constraints": ["No new dependencies"],
  "acceptance_checks": {"AC-1": ["python -m pytest tests/test_search.py"]},
  "reproduction_commands": ["python -m pytest tests/test_search.py"],
  "questions": {"Q-1": "Should an empty query return no results?"},
  "answers": {}
}
```

```sh
task-harbor contract --task SEARCH-1 --file agreement.json
task-harbor manage
task-harbor questions --run-id RUN_ID
task-harbor answer --run-id RUN_ID --task SEARCH-1 --question Q-1 --text "Yes, return an empty list"
task-harbor resume --run-id RUN_ID
```

Acceptance IDs follow the order in the backlog: AC-1, AC-2, and so on. Unanswered
questions block the task. A plan reviewer can also ask questions; only the
operator supplies executable commands. Importing a changed agreement affects
future runs, not agreements already saved in a run.

`allowed_paths` uses Python fnmatch patterns against repository-relative paths.
Changes outside those paths fail QA. Other constraints are supplied to the agents
and require review; they are not all mechanically enforceable.

Set `workflow` to `adaptive` to skip model planning and plan review for low-risk
tasks only when all criteria have checks, allowed paths are declared, and every
question is answered. Independent QA and a focused code review remain. Standard
is the default. Repeated identical failures with an unchanged Git tree stop after
`repeated_failure_limit` attempts; use retry after addressing the cause.

## Inspect what actually happened

```sh
task-harbor review --run-id RUN_ID --task SEARCH-1
task-harbor review --run-id RUN_ID --html review.html
task-harbor feedback --run-id RUN_ID --task SEARCH-1 --outcome accepted --minutes 5
```

Press E on a selected dashboard task to open its evidence. Reports show the
checkpoint, executed commands and output, acceptance evidence, reproduction
before/after, complete per-file diffs, and human feedback. Review flags call out
dependency changes, removed assertions, skipped tests, and scope violations.
Flags are heuristics, not vulnerability or correctness guarantees.

Model code review receives every diff chunk; completed chunks are cached for
resume. Binary files still require an appropriate external inspection. Large
diffs can increase review calls. Command output remains bounded by
`evidence_max_chars`; it is separate from the complete diff record.

For browser tests or other checks that produce files, set `verification_artifacts`
to exact relative output paths, for example `["test-results/search.png"]`. Existing
tracked files may not be modified. Files up to 20 MiB each are retained under the
run's `artifacts/` folder with SHA-256 hashes; missing, oversized, and escaping
paths are recorded. You supply the browser test command; Harbor does not invent
browser tests or interpret screenshots automatically. Artifacts and reports are
local files and may contain project data.

Feedback is an append-only operator record, separate from model QA. Review minutes
are self-reported; they are not measured automatically. Reports preserve each
entry and sum its minutes, so record incremental time rather than a running total.
Preflight, evidence viewing, feedback, and clarification answers make no model
calls. Checks consume local compute. Adaptive execution can reduce model calls;
focused reviews and large diffs can increase them.
