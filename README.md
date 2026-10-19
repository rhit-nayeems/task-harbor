# Task Harbor

**Bring autonomous engineering work safely into port.**

Task Harbor is a local engineering supervisor for Claude Code and GPT models through Codex. Give it a Git
repository and a Markdown backlog: it plans work, implements in isolated
worktrees, verifies checkpoint commits, and integrates passing changes on a
local branch. Python controls the workflow; the selected coding agent supplies engineering judgment.

Python 3.11+ · No runtime Python dependencies · Windows and Linux

## Quick start

Requires Git, an authenticated Claude Code or Codex CLI, and a target repository with at
least one commit and a configured Git author.

```powershell
python -m pip install -e .
task-harbor --repo "C:\path\to\app" init
# Edit the generated BACKLOG.md with real tasks and acceptance criteria.
task-harbor --repo "C:\path\to\app" validate
task-harbor --repo "C:\path\to\app" doctor
task-harbor --repo "C:\path\to\app" manage
```

`doctor` makes one small model call. `validate`, status, reports, and control
commands do not. The legacy `opus-harbor` and `opus-manager` commands and `python -m opus_manager`
remain supported. Install from this toolkit's directory; `--repo` selects the
application to manage.

## Use GPT through Codex

Install the Codex CLI and authenticate with `codex login`. Set these fields in
`.manager/config.json` after initialization, before starting a **new** run:

```json
{
  "provider": "codex",
  "model": "gpt-6.1-sol",
  "effort": "medium",
  "codex_bin": "codex",
  "max_agent_calls": 100,
  "max_task_agent_calls": 20,
  "max_run_cost_usd": null,
  "max_call_cost_usd": null
}
```

Choose a GPT model available to your Codex account. The example uses
`gpt-6.1-sol`; access depends on your account, client, and workspace. See the
[official model list](https://learn.chatgpt.com/docs/models).

Then run `task-harbor --repo <repo> doctor` and `manage`. The same provider handles
planning, implementation, QA, diagnosis, and review. To use Claude, set
`provider` to `claude` and `model` to `opus` (the defaults), or another supported
Claude model. Existing configurations migrate to `provider: "claude"`.

Runs persist their provider. Switching providers requires a new run so a Claude
session ID is never sent to Codex or vice versa. GPT repairs resume the exact
Codex thread; clean restarts create new threads. GPT token counts are recorded
from JSONL completion events. No dollar price is inferred from token counts.

| Control | Claude Code | Codex / GPT |
| --- | --- | --- |
| Run/task agent-call limits | Supported | Supported |
| Process timeout | Supported | Supported |
| CLI turn limit (`max_turns_*`) | Supported | Not available; use timeouts/call limits |
| Dollar caps | Estimated CLI caps | Rejected; set both dollar settings to `null` |
| Analysis and QA | Plan permissions / disposable QA | Read-only sandbox |
| Implementation | Edit permissions / isolated worktree | Workspace-write sandbox, shell network disabled |
| Session repair | Exact Claude session | Exact Codex thread |

Codex runs unattended with approval policy `never`. It never requests sandbox
bypass. Read-only QA may be unable to run tests requiring writes; configure those
commands in `verification_commands` so the Python harness executes them in the
disposable worktree first. CLI sandbox behavior depends on OS configuration; use
`doctor` to verify your setup. User config is excluded with `--ignore-user-config` while saved authentication
is reused. Project/managed configuration and external tools are still subject to
the installed CLI's behavior; a filesystem sandbox is not a universal boundary
for external services. Use a current Codex CLI supporting this flag. On Windows, npm installations use Node's Codex entry point
directly, avoiding shell-wrapper quoting. `codex_bin` can also point to a native
executable. CLI integration follows the
[official non-interactive guide](https://learn.chatgpt.com/docs/non-interactive-mode).

## How it works

1. Validate dependencies and acceptance criteria. Select eligible work by priority.
2. Run up to four independent planners, then review each plan.
3. Implement one task at a time in its own Git branch and worktree.
4. Create a checkpoint and run configured shell checks in a disposable worktree.
5. If checks pass, ask independent agent QA for evidence covering every acceptance ID.
6. Merge passing work into a local integration branch.
7. Review cumulative changes every three passes by default. Review fixes receive independent QA and re-review.

The first two failed QA attempts resume the same implementer. A third failure
triggers independent diagnosis and a new implementer session with a clean evidence
packet. The generation limit applies to both task failures and integration conflicts.
Current code is retained; the previous conversation is not.

Nothing is automatically pushed, published, deployed, or merged into your original
branch. The human backlog is updated in your original checkout.

## Lower overhead by default

- Deterministic priority/dependency scheduling avoids routine manager-selection calls.
- Backlog-only integration commits do not invalidate approved plans.
- Failed configured checks skip model QA and go straight to repair evidence.
- Successful harness checks are supplied to QA to avoid unnecessary repetition.
- Reports, progress state, and budget accounting use Python rather than a model.
- Final review of a partial batch is opt-in; periodic review remains enabled.

These changes reduce avoidable calls, but savings depend on the task and retries.
No token-saving percentage or production success rate is claimed.

## Backlog

See [BACKLOG.example.md](BACKLOG.example.md). Each task has an ID, priority,
dependencies, and observable acceptance criteria:

```markdown
## AUTH-001 — Fix refresh-token rotation
- **Priority:** critical_bug
- **Status:** UNPLANNED
- **Dependencies:** —
- **Acceptance criteria:**
  - Reusing a rotated refresh token fails
  - Existing valid sessions continue working
- **Next action:** Plan the task
```

Priorities: `blocker`, `critical_bug`, `high_risk`, `core`, `low_risk`, `polish`.
Criteria receive stable positional IDs (`AC-1`, `AC-2`, …) within the persisted
run. QA must cover each exactly once. Do not change task intent during an active
run; resumed runs use persisted intent, not edits to the Markdown board.

## Controls and visibility

```powershell
task-harbor --repo "C:\path\to\app" status --run-id RUN_ID
task-harbor --repo "C:\path\to\app" report --run-id RUN_ID
task-harbor --repo "C:\path\to\app" report --run-id RUN_ID --html report.html
task-harbor --repo "C:\path\to\app" stop --run-id RUN_ID
task-harbor --repo "C:\path\to\app" resume --run-id RUN_ID
task-harbor --repo "C:\path\to\app" retry --run-id RUN_ID --task AUTH-001
task-harbor --repo "C:\path\to\app" cleanup --run-id RUN_ID
```

`stop` is graceful: in-flight calls finish, then the supervisor pauses at the next
agent/cycle boundary. It does not terminate running child processes. Ctrl+C also
records a pause when handled by the supervisor. An abrupt process exit may leave
child processes running; stop those before resuming.

`retry` requires an inactive run and a blocked task. It resets task retry counters,
retires the implementer session, and records an operator event. Plans rejected by
review still require approval. Dependencies remain enforced. Usage budgets never
reset on retry/resume. Resume explicitly clears a stop request.

HTML reports are offline snapshots, with no server, external assets, or model
calls. They show task status, blockers, next actions, and reported usage. JSON
reports also expose dependencies, checkpoint IDs, and per-task usage. Full QA and
review evidence stays in the run artifacts.

## Configuration

Edit `.manager/config.json` while the manager is stopped. New fields migrate into
older configurations automatically.

```json
{
  "provider": "claude",
  "model": "opus",
  "effort": "medium",
  "scheduler": "deterministic",
  "max_active_planners": 4,
  "max_agent_calls": 100,
  "max_task_agent_calls": 20,
  "max_run_cost_usd": 25,
  "max_call_cost_usd": 3,
  "verification_commands": ["python -m pytest"],
  "verification_timeout_seconds": 300,
  "evidence_max_chars": 12000,
  "qa_passes_per_code_review": 3,
  "final_code_review": false
}
```

Budgets default to `null` (unset); the numbers above are examples, not generated
defaults. `scheduler: "model"` restores model-based work selection. Set
`final_code_review: true` to review remaining changes at the end of a partial batch.

Configured verification commands are trusted operator-provided shell commands,
executed automatically in the disposable QA worktree. Each has a timeout and
bounded captured output. Failures stop the command sequence and prevent model QA.
Commands that modify Git-visible files cause verification to be rejected. Install
dependencies as part of your configured commands when the worktree requires them.
Review-fix QA continues to select and execute its own checks.

### Budget semantics

Every dispatched agent call reserves a durable entry before execution, including
parallel planners. Call limits are cumulative across resumes; per-task limits
cover prompts attributable to a task, while cumulative review uses the run limit.
Cost reservations prevent planners from each claiming the same remaining budget.
Returned CLI estimates release unused reservations. Missing/interrupted cost
reports remain unknown and retain their reservation; they are not counted as free.
Raise a budget explicitly if more work is needed.

Dollar controls use Claude Code's `--max-budget-usd` and reported `total_cost_usd`.
They are **estimated spending controls, not a billing guarantee**: a model request
can overshoot the cap, and reported costs can differ from billing. Token totals
are reported usage, including separate cache counters when supplied by the CLI.
See the [official CLI reference](https://code.claude.com/docs/en/cli-reference).

## Persistence and isolation

```text
.manager/runs/<run-id>/
  state.json       # authoritative workflow state
  usage.json       # durable call reservations and reported usage
  events.jsonl     # ordered workflow/operator events
  plans/ qa/ reviews/ diagnostics/ logs/
```

Worktrees live beside the managed repository in
`.<repo-name>-opus-worktrees/<run-id>/`. Resume acquires the run lock before
reloading and reconciling state. State files use atomic replacement. Recovery
restarts interrupted planning, resumes implementation/repair, repeats checkpoint
QA, or retries integration. Cleanup also respects the run lock.

Claude permissions, protected-file checks, disposable QA worktrees, and a child
Git pre-push hook constrain normal agent behavior. They are not OS sandboxing.
Agents run with the launching account's filesystem/network access. Plan mode is
a Claude permission mode, not an operating-system read-only boundary.

## Development and evaluation

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Tests use simulated Claude/Codex responses and temporary real Git repositories. They cover
integration, clean restarts, budgets, duplicate acceptance evidence, interruption
recovery, locking, preflight failures, command timeouts, and operator controls.
CI runs on Windows and Linux with Python 3.11 and 3.14. Live provider compatibility
and engineering quality need separate evaluation; unit tests cannot establish them.

See [ARCHITECTURE.md](ARCHITECTURE.md), [WORKFLOW.md](WORKFLOW.md), and
[EVALUATION.md](EVALUATION.md) for implementation detail and evaluation guidance.
