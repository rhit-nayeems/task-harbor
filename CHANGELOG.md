# Changelog

## 0.3.0 — Opus Harbor

- Rename the distribution and primary CLI; retain the original import and CLI alias.
- Default to deterministic scheduling; skip backlog-only plan revalidation.
- Execute configured checks before task QA, retaining bounded evidence and checkpoint IDs.
- Require distinct acceptance coverage, using explicit criterion IDs.
- Persist call reservations, reported usage, and estimated cost across resumes.
- Add run/task call budgets and estimated dollar controls for real Claude invocations.
- Lock resume recovery and cleanup; preserve repair/fresh-session intent before calls.
- Enforce the generation ceiling in integration-conflict recovery.
- Add graceful stop, explicit task retry, JSON reports, and offline HTML snapshots.
- Add optional final cumulative review, config validation, and Windows/Linux CI.
- Add an opt-in independent smoke benchmark; no live quality claim.

## 0.2.0

Original backlog supervisor with isolated Git worktrees, independent QA, clean
context restarts, persisted run state, and periodic cumulative review.
