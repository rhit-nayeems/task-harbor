# Configuration

Settings live in `.manager/config.json` in the repository being managed. Stop
the manager before editing them. Missing settings use the defaults in
[`config.py`](../opus_manager/config.py).

## Common settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `provider` | `claude` | `claude` for Claude Code, `codex` for GPT through Codex |
| `model` | `opus` | Model identifier passed to the selected CLI |
| `effort` | `medium` | Reasoning effort; supported values depend on the model |
| `claude_bin` / `codex_bin` | `claude` / `codex` | CLI executable name or path |
| `max_active_planners` | `4` | Concurrent planners, from 1 to 4 |
| `scheduler` | `deterministic` | Select by priority/dependencies; `model` asks the agent to choose |
| `verification_commands` | `[]` | Shell commands to run before task QA |
| `verification_timeout_seconds` | `300` | Timeout for each verification command |
| `agent_timeout_seconds` | `3600` | Timeout for each agent invocation |
| `max_agent_calls` | `null` | Total calls allowed for the run |
| `max_task_agent_calls` | `null` | Calls allowed for an individual task |
| `max_run_cost_usd` / `max_call_cost_usd` | `null` | Estimated Claude spending caps |
| `qa_passes_per_code_review` | `3` | Review frequency |
| `final_code_review` | `false` | Review a remaining partial batch when the run ends |
| `keep_task_worktrees` | `true` | Keep task worktrees for inspection |

Priorities, in order: `blocker`, `critical_bug`, `high_risk`, `core`, `low_risk`,
`polish`. Dependencies must be complete before a task can start.

## Provider differences

| Control | Claude Code | Codex / GPT |
| --- | --- | --- |
| Call limits and process timeouts | Supported | Supported |
| Turn limits (`max_turns_*`) | Supported | Not supported |
| Estimated dollar caps | Supported | Rejected; use `null` |
| Analysis | Plan mode | Read-only sandbox |
| QA | Disposable worktree, no editor tools | Disposable worktree, read-only sandbox |
| Implementation | Edit permissions | Workspace-write sandbox, shell network disabled |
| Repair sessions | Resume the exact session | Resume the exact thread |

Codex uses `--ignore-user-config` and saved authentication, with approval policy
`never`. Project and managed configuration still follow the CLI's rules. Use a
current CLI supporting these options. On Windows, npm installations invoke the
Codex JavaScript entry point through Node; a native executable also works.

Model availability depends on your account. See the [Codex model list](https://learn.chatgpt.com/docs/models)
and [non-interactive CLI guide](https://learn.chatgpt.com/docs/non-interactive-mode).

## Verification commands

These are trusted shell commands that run automatically in a disposable
worktree. Add dependency installation if the worktree needs it. A failed command
stops the sequence and skips model QA. Output is bounded by `evidence_max_chars`
(default: 12000).

Checks that modify Git-visible files cause verification to be rejected. For
Codex, run checks that need filesystem writes here rather than relying on the
read-only QA agent. QA receives the command results and checks each acceptance
criterion. Review-fix QA selects its own checks.

## Usage and spending

Call counts persist across stops, retries, and resumes. Task limits apply to
calls associated with that task; scheduling and cumulative review use the run
limit. Increase a limit explicitly if you want a run to continue past it.

Calls reserve their budget before starting, including parallel planners. If a
call is interrupted without reporting cost, its reservation stays in place.
Missing cost is unknown, not zero. Codex reports tokens but no dollar cost.

Claude dollar caps use CLI estimates. A request can overshoot a cap, and estimates
can differ from billing. See the [Claude CLI reference](https://code.claude.com/docs/en/cli-reference).

## Run files

Each `.manager/runs/<run-id>/` directory contains:

- `state.json`: task states and session IDs
- `usage.json`: call reservations and reported usage
- `events.jsonl`: workflow and operator events
- `plans/`, `qa/`, `reviews/`, `diagnostics/`, `logs/`: supporting evidence

Worktrees live in `.<repo-name>-opus-worktrees/<run-id>/` beside the repository.
The old directory name is retained for compatibility. A run lock prevents two
managers from advancing the same run. Cleanup also respects that lock.

`retry` requires a stopped run and a blocked task. It resets task retry counters
and starts a new implementer session. Rejected plans still need review, and
dependencies remain enforced. `resume` clears an explicit stop request.
