# Task Harbor: technical and project status

Report date: October 20, 2026  
Source snapshot: `d6ead0625c94862ed4dd0efe7c11f183a6b2c4f5` on `main`  
Package version: `0.7.0`  
Repository: https://github.com/rhit-nayeems/task-harbor  
Website: https://task-harbor.sk-naimulnayeem.workers.dev/

This report describes the implementation inspected at the source snapshot above.
It separates implemented behavior, observed validation, and proposed work.
It is a point-in-time report, not a continuously updated dashboard or a security
audit. Later commits may change the behavior described here.

## 1. Current assessment

Task Harbor is a working local orchestration tool for coding agents. It takes a
Markdown backlog through planning, implementation, deterministic checks, model QA,
and integration into a separate local Git branch. It provides both a command-line
interface and a terminal dashboard.

The project has implemented the main trust and evaluation features discussed
during development: baseline preflight, consistent verification gates, task
evidence, structured clarification, direct-agent comparisons, adaptive workflows,
failure-loop detection, and explicit code-review coverage.

The remaining uncertainty is primarily empirical. Passing harness tests does not
establish that orchestration produces better code, reduces review time, saves
tokens, or attracts repeat users. The repository explicitly does not claim live
benchmark or comparison results.

| Area | Current state |
| --- | --- |
| CLI and dashboard | Implemented and covered by automated tests |
| Claude Code and Codex adapters | Implemented; real account/model compatibility still depends on the user's environment |
| Verification and evidence | Implemented, with important configuration-dependent limits |
| Recovery and usage control | Implemented; not an exactly-once execution system |
| Direct-agent evaluation | Runnable machinery; no published live comparison evidence |
| Distribution | Installable Python package from GitHub; not published to PyPI according to project documentation |
| Source availability | Public repository with MIT license |
| Website | Public static site on Cloudflare |
| Website delivery | Automatic deployment from relevant changes on `main`; verified successful |
| Release publishing | No GitHub releases returned by `gh release list` during inspection |
| Commercial/product validation | Not established by the repository or checks performed for this report |

## 2. What the tool does

### Inputs

The operator supplies a Git repository, a Markdown backlog, configuration, and an
authenticated agent CLI. A target repository needs an initial commit and a Git
author identity. Dirty repositories are rejected by default.

A backlog task contains an ID, title, priority, status, dependencies, and
acceptance criteria. IDs and dependency relationships are validated before work.
Optional task agreements specify allowed paths, risk, constraints, executable
acceptance checks, reproduction commands, and questions requiring human answers.

Configuration lives at `.manager/config.json` by default. The backlog defaults
to `BACKLOG.md`. Agent binaries, provider/model choice, limits, environment
requirements, verification commands, and workflow behavior are configurable.

### Normal execution

1. Load and validate the backlog and configuration.
2. Create a run with a pinned starting commit and a local integration branch.
3. Record baseline environment and check results before agent work.
4. Select eligible tasks using dependency and priority rules.
5. Plan up to four tasks concurrently and review their plans.
6. Implement one task at a time in its own Git worktree.
7. Create a checkpoint commit for the candidate implementation.
8. Run configured deterministic checks at that checkpoint in a disposable
   worktree, then obtain independent model QA.
9. Repair failed work within configured limits, or block/pause for intervention.
10. Merge passing work into the local integration branch.
11. Run cumulative code review at the configured cadence; verify review fixes
    before integrating them.
12. Preserve state, evidence, usage, and events for review and resumption.

The operator inspects the result on `manager/integration/<run-id>`. Task Harbor
does not automatically push the target repository or merge into its original
branch. Completion in the harness is distinct from human acceptance.

### Outputs

- Integration and task branches, checkpoint commits, and worktrees.
- Durable run state and event records.
- Plans, QA results, code-review findings, and coverage records.
- Executed verification commands, exit status, duration, bounded output, and
  timeout information.
- Per-task change evidence and complete per-file textual diffs.
- Optional retained verification artifacts with hashes.
- JSON/HTML run reports and task review reports.
- Append-only human feedback.
- Direct-agent comparison trial and aggregate result files.

## 3. Architecture and source map

The Python control layer owns scheduling constraints, Git operations, state,
verification, budgets, and recovery. Agent subprocesses supply planning,
implementation, diagnosis, and review judgments.

| Source | Responsibility |
| --- | --- |
| `opus_manager/cli.py` | Argument parsing and command dispatch |
| `opus_manager/tui.py` | Textual dashboard, run selection, task inspection, and operator actions |
| `opus_manager/desktop_actions.py` | Dashboard launch and action support |
| `opus_manager/orchestrator.py` | Main run lifecycle, planning, QA, repair, integration, review, and recovery |
| `opus_manager/models.py` | Task, priority, and manager-state data structures |
| `opus_manager/config.py` | Defaults, validation, loading, and configuration migration |
| `opus_manager/backlog.py` | Markdown task parsing and backlog output |
| `opus_manager/gitops.py` | Git repositories, branches, worktrees, checkpoints, and diffs |
| `opus_manager/state.py` | State serialization and atomic persistence |
| `opus_manager/agent.py` | Shared agent result abstractions |
| `opus_manager/providers.py` | Provider selection |
| `opus_manager/claude.py` | Claude Code process integration |
| `opus_manager/codex.py` | Codex process integration and JSONL validation |
| `opus_manager/prompts.py` | Role-specific prompts |
| `opus_manager/usage.py` | Usage reservations, accounting, and budget enforcement |
| `opus_manager/verification.py` | Timed shell-command execution with bounded evidence |
| `opus_manager/preflight.py` | Environment recipes, baseline checks, mutations, and artifact retention |
| `opus_manager/contracts.py` | Task agreement validation and adaptive eligibility |
| `opus_manager/evidence.py` | Diff evidence, review chunks, flags, and failure signatures |
| `opus_manager/operator_commands.py` | Preflight, agreements, answers, review, and feedback operations |
| `opus_manager/reporting.py` | Offline report generation |
| `opus_manager/comparison.py` | Direct-agent versus orchestrated comparison execution |
| `task_harbor/` | Public Python module entry point |
| `evaluations/run.py` | Small opt-in live benchmark fixture runner |

The internal package remains named `opus_manager` for compatibility. The public
package and primary command are `task-harbor`. Console aliases `opus-harbor` and
`opus-manager` remain configured. There is no `harbor` console entry point in the
inspected package metadata.

## 4. Providers, models, and usage

### Provider support

| Capability | Claude Code | Codex |
| --- | --- | --- |
| Provider configuration | `claude` | `codex` |
| Default/selection | Default model is `opus` | Explicit available `gpt-` model required |
| Authentication | User's installed/authenticated CLI | User's installed/authenticated CLI |
| Session continuation | Supported by adapter | Supported by adapter |
| Call limits and process timeout | Supported | Supported |
| Estimated dollar budgets | Supported, with request-boundary limitations | Unsupported; dollar settings must be null |
| Claude-style per-call turn control | Supported | Not claimed as equivalent |
| Cost reporting | Uses provider-reported information | Unknown costs stay unknown rather than becoming zero |

Provider identity is saved with a run. Switching provider on resume is rejected.
This is CLI integration, not a generic API gateway for arbitrary model vendors.
Support for a configured identifier does not prove that the user's account can
access that model.

Codex output must contain a valid thread, final response, and completed turn.
Malformed, failed, incomplete, or mismatched-session responses fail closed.

### Model consumption

Reading status, viewing evidence, generating reports, recording feedback, and
answering questions do not require model calls. Deterministic checks consume
local compute. `doctor` does make a model call.

Planning, implementation, model QA, diagnosis, and code review consume provider
usage. The deterministic scheduler avoids an extra scheduling model call by
default. Adaptive execution can omit planning calls for eligible tasks. Full
diff review can increase calls when changes are large.

The usage ledger reserves calls before dispatch and persists accounting.
Interrupted calls with unknown cost retain reservations. Dollar budgets are
estimates and may overshoot within a model request. Call count is not token count,
and no universal token reduction has been demonstrated.

## 5. Verification, clarification, and review

### Baseline and environment preflight

`preflight` suggests commands from recognizable project files without running
them. `preflight --run-checks` executes the operator's configured recipe in a
disposable worktree. Supported suggestions include common npm scripts, pytest,
Cargo, and Go tests.

Required executables and environment variables are checked. Setup commands run
before verification commands. Missing requirements, failed setup, or unexpected
worktree mutations produce an environment block.

A baseline is saved before model calls in a run. With `require_verification`
enabled, checks are mandatory and baseline failures stop progress. The default is
false for compatibility, so a project can record a failing baseline while working
on a known problem. Candidate checks must still pass when configured.

Baseline/candidate comparison uses command outcomes; matching failure status does
not establish matching root causes.

### Candidate and review-fix gates

Task checks execute at an exact checkpoint before model QA. A failed
deterministic check cannot be overridden by a model PASS. Acceptance IDs allow
criteria to be tracked distinctly.

Cumulative review fixes now also call the shared deterministic check machinery
in a detached QA worktree. Failed checks, environment blocks, and rejected QA
mutations prevent a PASS from being accepted. The earlier asymmetry between
ordinary task QA and review-fix verification is addressed in the implementation.

These checks prove only what the configured commands test. With empty check
configuration and `require_verification` false, the tool cannot provide the same
level of deterministic evidence as a properly configured project.

### Structured task agreements

Agreements support:

- Risk classification: low, normal, or high.
- Allowed path patterns.
- Out-of-scope work and textual constraints.
- Acceptance-ID-to-command mappings.
- Reproduction commands.
- Question and answer mappings.

Unanswered questions block the relevant task. Plan review can request
clarification, and only the operator supplies executable agreement commands.
Changes to imported agreements apply to future runs; persisted agreements are
used when resuming an existing run.

Allowed paths are mechanically checked with Python `fnmatch` patterns. Natural
language constraints and out-of-scope statements still require agent and human
judgment; they are not a complete policy enforcement system.

### Adaptive workflow and loop detection

The default workflow is `standard`. Under `adaptive`, a task can skip model
planning and plan review only when it is marked low risk, declares allowed paths,
has checks for every acceptance criterion, and has no unanswered questions.
Independent QA and focused code review remain.

Repeated failure detection uses a stable signature and unchanged Git tree to
stop unproductive retries. It does not claim to detect every semantic loop or
every sequence of different but equally unproductive edits.

### Coverage and evidence

Code review splits per-file textual diffs into bounded chunks, submits all chunks,
records coverage, and caches completed chunk results for resumption. Cache
identity includes commits, chunk contents, provider, model, and effort.

Coverage means content was submitted for review, not that the model understood
every issue. Binary files require appropriate external inspection. Command
output is still bounded independently of the complete textual diff record.

Review flags highlight patterns such as dependency changes, removed assertions,
skipped tests, and scope violations. These are heuristics, not correctness or
vulnerability guarantees.

Explicit verification artifacts can be retained up to 20 MiB each with SHA-256
hashes. Missing, oversized, symlinked, or escaping paths are handled explicitly.
Task Harbor does not generate browser tests or interpret screenshots by itself.

## 6. State, failure recovery, and boundaries

Task states include `UNPLANNED`, `PLANNING`, `PLAN_REVIEW`, `READY`,
`IMPLEMENTING`, `QA`, `QA_FAIL`, `QA_PASSED`, `CODE_REVIEW`, and `COMPLETE`.
Blocking is represented separately through reasons/metadata rather than a single
`BLOCKED` enum state.

`state.json` is the active run's source of truth. The Markdown backlog is the
human-facing task board. Resume reads saved task requirements rather than
silently replacing them with later backlog edits.

An operating-system-held per-run lock prevents two supervisors from advancing
the same run simultaneously. State is persisted around long-running operations.
Recovery maps interrupted states back into work that can be retried. QA-pass
accounting is checkpoint-aware to avoid double counting.

Repair starts with bounded same-session attempts. Further failures can invoke
diagnosis and a fresh implementer context. A fresh context still sees current
repository contents; it does not mean reverting all code changes.

Known operational boundaries:

- Worktrees isolate Git changes, not operating-system access.
- Agent and verification commands execute locally with host permissions.
- Setup commands can change installed dependencies outside a worktree.
- Protected-path checks are useful guardrails, not a sandbox.
- Hard crashes can leave child processes running; operators may need to stop
  those processes before resuming.
- Review-fix recovery may repeat cumulative review; individual turns are not
  guaranteed exactly once.
- A stop request waits for an agent boundary rather than guaranteeing instant
  cancellation.
- Cleanup removes worktrees while preserving branches and logs.
- Saved reports, artifacts, and command output can contain private project data.

## 7. Important defaults

These values come from `opus_manager/config.py`, not recommended settings for
every project.

| Setting | Default |
| --- | --- |
| Provider / model / effort | `claude` / `opus` / `medium` |
| Scheduler | `deterministic` |
| Workflow | `standard` |
| Concurrent planners | 4 maximum |
| Implementation concurrency | One task at a time |
| Agent timeout | 3,600 seconds |
| Verification command timeout | 300 seconds |
| Evidence bound | 12,000 configured units; command output is read as bounded bytes and decoded |
| Same-session repair attempts before restart | 2 |
| Fresh implementer generations | 3 |
| Plan reworks | 2 |
| Cumulative review fix retries | 2 after initial attempt |
| QA passes per cumulative review | 3 |
| Final code review | Disabled |
| Repeated unchanged-failure limit | 4 |
| Maximum manager cycles | 1,000 |
| Run/task call caps | Unset |
| Run/call dollar caps | Unset |
| Verification/setup commands | Empty |
| Require verification | False |
| Allow dirty repository | False |
| Keep task worktrees | True |

Per-role Claude turn defaults are manager 12, planner 30, implementer 80, QA 40,
reviewer 50, and diagnosis 50. These should not be represented as equivalent
enforced Codex turn limits.

## 8. User interface and command surface

Running `task-harbor` or `python -m task_harbor` with no subcommand opens the
Textual terminal dashboard. It includes first-run setup, validation, run
selection, task details, progress/events, usage, evidence, and help.

The run selector is meaningful only after the selected repository has a saved
run. The dashboard refreshes periodically. Starting or resuming agent work
requires a confirmation showing its configuration; passive monitoring uses no
model calls. Closing the dashboard does not stop an already launched run.

| Command group | Commands |
| --- | --- |
| Setup/help | `init`, `guide`, `--help`, `--version`, `validate`, `doctor` |
| Run lifecycle | `manage`, `resume`, `stop`, `retry`, `cleanup` |
| Monitoring | `tui`, `status`, `report` |
| Verification and intent | `preflight`, `contract`, `questions`, `answer` |
| Human review | `review`, `feedback` |
| Evaluation | `compare` |

`--repo` precedes the subcommand. Run-oriented commands use `--run-id`.
Reports support JSON and/or HTML depending on the command. Human feedback records
accepted/rejected/needs-changes outcomes and incremental review minutes.
Those minutes are self-reported, not measured automatically.

## 9. Evaluation and validation status

### Automated tests

Tests use simulated agent responses and real temporary Git repositories. Coverage
areas include backlog parsing, provider adapters, Git operations, recovery,
orchestrator integration, hardening, trust workflows, CLI help, dashboard behavior,
and desktop launch actions.

The Tests workflow runs on Windows and Ubuntu with Python 3.11 and 3.14. It
installs the package, runs pytest, exercises CLI help/guide, and builds a wheel.
At the inspected source snapshot, the workflow completed successfully:

https://github.com/rhit-nayeems/task-harbor/actions/runs/39370735550

During this report's preparation, `python -m pytest` completed locally on Windows:
**102 passed in 120.06 seconds**. No live provider calls were made by this test
run. This confirms the current automated suite passes, not exhaustive correctness.

### Live evaluations

`evaluations/run.py` provides three small Python tasks and an external grader.
Fixture preparation is offline; `--live` consumes provider usage. This smoke
benchmark is not representative evidence for production repositories.

`task-harbor compare` prepares or executes matched trials at a pinned source
commit. It creates separate clones for the direct-agent and Harbor arms, uses
the same configured provider/model/effort and task/environment recipe, and
shuffles arm ordering with a fixed seed.

The direct arm is one agent invocation with its tool loop. Harbor uses its
configured workflow. Trial outputs retain checkout state, usage, elapsed time,
outcomes, configuration, and provider CLI version. Failed trials remain in the
aggregate results.

Limitations:

- Equal total tokens or total agent turns are not enforced between arms.
- Graders are omitted from prompts but are not isolated from host access.
- Passing the independent grader is not the same as human acceptance.
- Human outcome and active time need separate collection.
- Missing provider costs must not be treated as zero.
- No live benchmark or comparison results are claimed in the current project
  documentation, and none were run for this report.

## 10. Website and deployment

The website is a static landing page, not a hosted interface for executing
Task Harbor. It has no application backend, accounts, database, or provider calls.

Source consists of `website/index.html`, `style.css`, `app.js`, and `mark.svg`.
`build.mjs` copies those four files to `website/dist/`. Runtime JavaScript handles
installation-command copying. The review command disclosure uses native HTML.
Fonts load from Google Fonts with local fallbacks.

The design uses cobalt and cream, a condensed wordmark, a narrower desktop
container, responsive layout, installation instructions, workflow explanation,
specifications, and contribution links. The task example is explicitly
illustrative: it explains a request, test results, and human review. It is not
live output or a captured benchmark result. License information appears once in
the footer.

Hosting is Cloudflare Workers Static Assets at the public URL at the top of this
report. No executable Worker handler is deployed. The configured Worker name is
`task-harbor`. No custom domain is configured in the inspected deployment.

Deployment tooling uses the pinned `cf` CLI beta dependency and the lockfile's
resolved Wrangler build tool. `cloudflare.config.ts` defines the Worker and
`wrangler.config.ts` points to `dist/`. These are development/deployment
dependencies, not website runtime dependencies.

### Automatic delivery

`.github/workflows/website.yml`:

1. Runs for website/workflow changes pushed to `main`.
2. Checks relevant pull requests without publishing them.
3. Allows manual runs.
4. Installs locked dependencies on Node 22.
5. Checks JavaScript syntax and builds the site.
6. Performs a deployment dry run.
7. Deploys the prebuilt output only from `main`, outside pull-request events.
8. Fetches all four public files, follows redirects, and compares bytes with
   the build, retrying briefly for propagation.

Credentials are stored as GitHub Actions repository secrets and exposed only to
the deployment step. The deployment token has Workers Scripts Write and Account
Settings Read for the hosting account. It is account-scoped, not restricted to
one Worker; repository maintainers should understand this boundary.
No secret values are included in this report.

The latest website run at the inspected snapshot passed, including deployed-file
verification:

https://github.com/rhit-nayeems/task-harbor/actions/runs/39370735535

This checks artifact delivery, not appearance, accessibility, or every browser
interaction. Visual and interaction regression checks are not currently part of
the deployment workflow.

## 11. Distribution and documentation

The package requires Python 3.11+ and Textual `>=1,<2`. Git, the selected provider
CLI, and provider authentication are external prerequisites.

Current supported installation:

```sh
python -m pip install "git+https://github.com/rhit-nayeems/task-harbor.git"
task-harbor guide
```

The repository also documents pipx installation and the Python-module fallback.
Installation from `main` follows current repository contents; a tagged release
would provide a clearer reproducible release target.

Existing documentation includes README, configuration, verification, architecture,
workflow, evaluation, changelog, contribution guide, and terminal screenshots.
Some architectural prose still refers to earlier versions and Claude Opus alone.
The README's short command table does not enumerate all commands now present in
the CLI parser. This report uses the current source when those descriptions
differ.

The MIT license is present in the repository and package metadata. Copyright
and package authorship identify `rhit-nayeems`.

## 12. Gaps and recommended next work

These are recommendations, not features claimed as implemented.

| Priority | Work | Completion evidence |
| --- | --- | --- |
| 1 | Run representative live comparisons for both providers | Versioned fixtures, repeated trials, independently graded outcomes, costs/tokens where available, and failure records |
| 1 | Observe first-time setup with real developers | Time to first run, setup failures, unanswered questions, and successful completion records |
| 1 | Validate practical review value | Human review minutes, acceptance/rejection, missed regressions, and repeat usage |
| 2 | Make verification setup harder to overlook | Users see whether checks are configured and understand what an unverified run means |
| 2 | Finish release packaging | Versioned release/tag, tested install/upgrade paths, and PyPI publishing if desired |
| 2 | Refresh older documentation | Architecture/provider wording and full command reference match implementation |
| 2 | Add website browser checks | Mobile/desktop layout, keyboard interaction, copy fallback, links, and accessibility checks in CI |
| 3 | Expand recovery and environment testing | Live interruption scenarios, long-running child processes, dependency setup failures, and larger repositories |
| 3 | Review deployment credential scope and lifecycle | Documented rotation/revocation and least-privilege options supported by the host |

Additional providers, parallel implementers, cloud execution, and a hosted team
dashboard are possible future directions. They are not necessary to test the
current product hypothesis and should not be presented as existing capabilities.

## 13. What can responsibly be claimed today

Task Harbor can orchestrate a Markdown coding backlog with Claude Code or Codex,
preserve local run state, execute configured checks, expose review evidence, and
provide a framework for direct-agent comparisons.

The inspected implementation and successful CI support those engineering claims.
They do not support claims that it consistently outperforms direct agents,
reduces total spending, eliminates review, is safe for untrusted code, or has
demonstrated product-market fit.

The next useful milestone is a documented set of real users completing real tasks,
with independent outcome checks and measured review effort.
