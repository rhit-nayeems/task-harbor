# Changelog

## 0.8.0

- Add a provider-free demo with a scripted fix, real tests, and a review report.
- Add guided setup with required verification and a default 20-call run limit.
- Show changed files, check outcomes, acceptance evidence, and checkpoint-specific human review in reports.
- Record optional supervision and repair time alongside human review time; add pilot instructions.

## 0.7.1

- Publish corrected PyPI installation instructions and absolute documentation links.

## 0.7.0 additions

- Add a read-only `check` command for setup, verification, and usage-limit gaps.
- Add `runs` with status filters and JSON summaries, including corrupt-run diagnostics.
- Both commands work without provider calls or execution of project recipes.

## 0.7.0

- Add preflight recipes and baseline checks before model work.
- Add task agreements, clarification answers, and an opt-in low-risk workflow.
- Record complete diffs, reproduction results, check artifacts, and human feedback.
- Check review fixes deterministically and stop unchanged failure loops.
- Add opt-in direct-agent comparisons with independent graders and failure records.

## 0.6.0 — Project and run controls

- Add setup, validation, confirmed start/resume, and stop controls to the dashboard.
- Hide the run picker until runs exist and explain what a run means.
- Keep launch logs, show launch failures, and select newly launched runs automatically.

## 0.5.0 — Terminal dashboard

- Include the dashboard in standard installs; add setup guide, F1 help, progress,
  first-run instructions, and reproducible terminal screenshots.

- Open the dashboard when no command is given; add `python -m task_harbor`.

- Add an optional terminal dashboard: run picker, task details, recent events,
  usage totals, keyboard navigation, and automatic refresh without model calls.
- Add dashboard interaction tests to the Windows and Linux CI jobs.

## 0.4.0 — Task Harbor

- Add GPT through Codex CLI, including JSONL usage and exact thread resumption.
- Introduce a provider factory and shared result/error types.
- Persist provider identity and reject cross-provider run resumes.
- Use read-only Codex analysis/QA and workspace-write implementation.
- Reject unsupported Codex dollar caps; retain call limits and timeouts.
- Rename the project and primary command; keep both legacy command aliases.
- Add adapter, error handling, Windows launcher, and full GPT workflow tests.

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
