# Architecture notes

## Control plane vs reasoning plane

**Control plane (Python):** state transitions, dependency gates, priority candidates, planner cap, local Git isolation, session persistence, QA independence, retry counters, clean-context boundary, plan-staleness checks, post-merge review accounting, interruption recovery, protected paths, atomic state persistence, and stopping conditions.

**Reasoning plane (Claude Opus):** scheduling judgment among eligible work, repository analysis, planning, plan quality judgment, implementation strategy, QA evidence selection, investigator-vs-auditor classification, diagnosis, and code-review severity.

The harness intentionally avoids reducing engineering tasks to line-by-line generated instructions.

## Why only planners are parallel in v0.3

The supervisor's workflow clearly benefits from parallel planning. Parallel write-capable agents are a different problem: even with independent worktrees, their branches are based on snapshots that can diverge and create semantic conflicts that Git cannot detect. v0.3 therefore serializes implementations while leaving the worktree/branch boundaries in place.

A future version can safely add parallel implementers by adding a manager-level conflict-risk decision, file/semantic overlap signals, integration queues, and first-class conflict repair. It should not simply raise a thread-pool size.

## Clean restart semantics

"Poisoned context" means conversation/reasoning context, not automatically poisoned repository state. The replacement implementer sees the current code because the current repo state is evidence. It does not receive the prior implementer's transcript or recommended fix.

## Durable transition semantics

Agent calls are not treated as atomic. Before a long-running implementation or QA call, the manager persists the transition and relevant checkpoint. On resume, transient states are converted into idempotent recovery work: restart a planner, resume/freshen implementation, repeat QA at the exact checkpoint, continue a repair from persisted evidence, or retry a QA-passed merge. QA pass accounting is keyed by checkpoint so replay cannot double-count it.

An OS-held per-run lock prevents two manager processes from advancing the same state and event stream concurrently. The operating system releases the lock if the owning process exits, so a service supervisor can safely restart and resume the run.

Operational blocks such as exhausted plan rework, repeated QA generations, and integration conflicts are distinct from derived dependency/acceptance blocks. Recomputing dependencies cannot accidentally erase a human-escalation condition.

## Review cadence

`qa_passes_since_review` is durable state. On the configured threshold, the reviewer examines the cumulative integration-branch diff since `last_review_commit`. Blocking findings go through a separate review-fix → QA recheck → re-review loop before the checkpoint advances.

## Source of truth

`state.json` is the runtime source of truth for an active run. `BACKLOG.md` is the human task board and is synchronized by the manager. On a new run, durable task intent is imported from `BACKLOG.md`; on resume, the exact persisted run state is used.

## v0.3 usage and verification

Scheduling defaults to Python priority ordering. Model selection is optional.
Backlog-only diffs do not require plan revalidation. Configured checks run before
model task QA, with checkpoint IDs, exit codes, timeouts, and bounded output.
QA must cover distinct acceptance IDs; criterion-text matching remains supported
for older responses only when it unambiguously identifies a single criterion.

Usage reservations live in a separate atomic JSON ledger guarded by a thread
lock; production calls run under the supervisor process lock. Each call is
reserved before dispatch. Unknown interrupted costs retain their reservation.
Dollar controls are estimates and can overshoot at request boundaries. Task
budgets count task-specific prompts; scheduling and cumulative review count only
against the run. Reports read persisted state and usage without calling a model.

Resume reloads and reconciles state after acquiring the run lock. Repair and
fresh-restart intent are saved before calls. Review-fix work is still recovered
by repeating cumulative review; individual review-fix turns are not exactly-once.
A hard crash can leave child processes alive. Stop them before resuming.
