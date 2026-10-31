# Implementation status: 0.9.0

This tracks the engineering work proposed after the YC discussion. It does not
establish traction or predict admission to an accelerator.

| Planned change | Implementation | Validation |
| --- | --- | --- |
| Try Harbor without a provider | `demo` creates a separate repository, applies a labeled scripted fix, runs real tests, and writes review evidence. | Demo checks reproduce failure and pass after the fix without creating a provider client. |
| Guided first real task | Interactive `setup` collects configuration and a first task for a new backlog. `add-task` collects subsequent tasks and acceptance criteria. | New-task, duplicate-ID, input-validation, and existing-text preservation checks. |
| Dashboard onboarding | Set up opens a configuration and task form; checks and call limits use the same setup implementation as the CLI. Save and Cancel remain visible. | Dashboard setup/save, cancel, validation-error, and launch-cancellation tests. |
| Clear review evidence | Task reviews show changed files, checkpoint matching, acceptance evidence, checks, risks, and checkpoint-specific human feedback. | Evidence and review regression tests. |
| Measure human effort | Normal run feedback records review, supervision, and repair time. Comparison feedback records cumulative effort and regressions per trial. | Nonnegative/finite input checks; latest-assessment and stale-result tests. |
| Compare both workflows | `compare-report` produces text, JSON, or standalone HTML. Unsuccessful and scheduled-but-missing trials stay visible. Effort per accepted task requires complete feedback for that arm. | Cohort, abandoned-effort, missing-feedback, missing-schedule, stale-feedback, and independent-vs-human outcome tests. |
| Consistent public instructions | README, terminal help, and website describe demo, guided setup, checks, task creation, and human review. Public copy focuses on Python maintenance backlogs. | Website production build and desktop/mobile layout checks; CLI help checks. |
| Prepare pilots | Protocol, blank worksheets, interview questions, and sourced recruitment research are in `docs/` and `evaluations/pilot-templates/`. | Documentation link checks. No fabricated customer records. |

## What these changes do not establish

- No new live provider evaluations have been run; they remain deferred at the owner's request.
- No participants have been recruited through this work and no invitations have been sent.
- Repeat usage, production outcomes, willingness to pay, and commercial demand remain unmeasured.
- The Python maintenance-team segment is an initial hypothesis, not a validated customer profile.
- Provider costs and token totals can be incomplete. Reports label missing measurements.
- Agent worktrees are not a security sandbox. Passing checks are not a correctness guarantee.

Tests use simulated providers where agent responses are needed. Demo behavior
and synthetic test results must not be presented as customer or live-agent results.

For release artifacts and the exact source revision, see the
[0.9.0 release](https://github.com/rhit-nayeems/task-harbor/releases/tag/v0.9.0).
