# Task Harbor

Task Harbor is a command-line tool that runs coding tasks with Claude Code or
Codex. It reads a Markdown backlog, plans each task, makes changes in separate
Git worktrees, and checks the results before merging them into a local branch.

It does not push changes or merge them into your original branch. You review the
result on `manager/integration/<run-id>`.

## Check the work before accepting it

Configure tests once, then inspect the exact commands, checkpoint, and full diff
for each task. Task agreements capture scope and unanswered questions. A failed
check stops approval; a missing environment pauses work before more model calls.

- [Set up checks and task agreements](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/VERIFICATION.md)
- [Compare Harbor with a direct agent](https://github.com/rhit-nayeems/task-harbor/blob/main/EVALUATION.md)

```sh
task-harbor preflight
task-harbor review --run-id RUN_ID --html review.html
```

In the dashboard, press **E** for task evidence or **P** for suggested checks.

## Install

You need Python 3.11+, Git, and either Claude Code or Codex installed and signed in.
The repository you want to work on must have at least one commit and a configured
Git author.

Install the Python package from PyPI:

```sh
python -m pip install task-harbor
task-harbor --version
task-harbor guide
```

The dashboard is included. Releases are available on [PyPI](https://pypi.org/project/task-harbor/).

<details>
<summary>Isolated install, upgrades, and command-not-found fixes</summary>

With pipx installed, use an isolated application environment:

```sh
pipx install task-harbor
pipx ensurepath
```

Restart your terminal after changing PATH. For a regular pip installation,
`python -m task_harbor` works with the same arguments if the executable is not
on PATH. Use the same Python interpreter you installed with.

Upgrade a pip installation:

```sh
python -m pip install --upgrade task-harbor
```

For pipx, use `pipx upgrade task-harbor`. Uninstall with `python -m pip uninstall
task-harbor` or `pipx uninstall task-harbor`, respectively.

</details>

[First run](#start-a-run) · [Commands](#cli-commands) · [Configuration](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/CONFIGURATION.md)

## Terminal dashboard

![Task dashboard with sample data](https://raw.githubusercontent.com/rhit-nayeems/task-harbor/main/docs/terminal-dashboard.svg)

<details>
<summary>See first-run setup and built-in help</summary>

![First-run screen](https://raw.githubusercontent.com/rhit-nayeems/task-harbor/main/docs/terminal-welcome.svg)
![Built-in help screen](https://raw.githubusercontent.com/rhit-nayeems/task-harbor/main/docs/terminal-help.svg)
![Task evidence screen with sample data](https://raw.githubusercontent.com/rhit-nayeems/task-harbor/main/docs/terminal-evidence.svg)

</details>

These are captures of the actual terminal interface. The task dashboard uses
sample run data. Open it inside your project:

```sh
task-harbor
```

Running `task-harbor` (or `python -m task_harbor`) without a command opens the
dashboard for the current directory. `--help` lists the other commands.

The dashboard shows saved runs, task status, dependencies, recent events, agent
calls, and reported costs. Select a run with the picker and use the arrow keys
to inspect tasks. Tab changes panes, F1 opens help, `r` refreshes, and `q` exits. It also
refreshes automatically every two seconds.

A run is one execution of your backlog. The run picker appears only after a run
exists in the selected project.

Use **Set up** to create the configuration and sample backlog, edit those files,
then click **Validate**. **New run** and **Resume** show the provider, model, and
call limit before you confirm agent work. **Stop** requests a pause after current
calls finish. Closing the dashboard does not stop a launched run.

Viewing progress does not consume tokens. Starting or resuming work does.
Launch output is saved in `.manager/launch-logs/` (or your configured manager
directory). Launch errors appear above the task list. Unreported costs are unknown.
Use `tui --run-id <id>` to open a specific saved run. All commands below still work
without the dashboard.

## Start a run

Replace `path/to/your-app` with the repository you want Task Harbor to work on.
Use `--repo` before the command.

```sh
task-harbor --repo "path/to/your-app" init
```

This creates `.manager/config.json` and a sample `BACKLOG.md` in that repository.
An existing backlog is kept. Replace the sample task with your own work:

```markdown
## BUG-001 — Fix empty search results
- **Priority:** critical_bug
- **Status:** UNPLANNED
- **Dependencies:** —
- **Acceptance criteria:**
  - An empty search shows a message instead of crashing
  - Existing search tests pass
- **Next action:** Plan the task
```

Use a different ID for each task. List dependency IDs separated by commas.
See [BACKLOG.example.md](https://github.com/rhit-nayeems/task-harbor/blob/main/BACKLOG.example.md) for a longer example.

### Choose Claude or GPT

Edit `.manager/config.json` before starting. Claude is the default:

```json
{
  "provider": "claude",
  "model": "opus",
  "effort": "medium"
}
```

For GPT, sign in with `codex login` and change these fields:

```json
{
  "provider": "codex",
  "model": "gpt-6.1-sol",
  "effort": "medium",
  "max_run_cost_usd": null,
  "max_call_cost_usd": null
}
```

Use a model available to your account. Provider choice applies to the whole run;
you cannot switch providers when resuming it.

### Set checks and limits

Add your project's test or build commands to the configuration. For example:

```json
{
  "verification_commands": ["python -m pytest"],
  "max_agent_calls": 100,
  "max_task_agent_calls": 20
}
```

These call limits are examples; the defaults are unlimited. Both providers support
call limits and timeouts. Only Claude supports estimated dollar caps. Codex
requires both dollar-budget settings to be `null`.

Now validate the backlog, check the selected agent, and start:

```sh
task-harbor --repo "path/to/your-app" validate
task-harbor --repo "path/to/your-app" doctor
task-harbor --repo "path/to/your-app" manage
```

`doctor` makes a model call. `manage` uses model calls throughout the run and
prints a run ID. Save that ID to check progress or resume later.

## CLI commands

Before spending model usage, run `task-harbor check`. It checks Git, the backlog,
configuration, agent executable availability, required environment, and whether
verification and call limits are configured. It reads local files without
creating configuration, running project commands, or testing provider
authentication. Errors return exit code 2; warnings explain missing safeguards.
Use `check --json` for structured results.

Find saved run IDs with `task-harbor runs`, or filter with
`task-harbor runs --status paused`. `runs --json` includes task counts, blocked
counts, stop reasons, and integration branches. Unreadable runs are reported
without hiding healthy ones. These are persisted snapshots: “unfinished” does
not mean a process is currently running.

All commands accept `--repo` before the command. Replace `RUN_ID` below with the
ID printed by `manage`.

| Command | What it does |
| --- | --- |
| `guide` | Setup, usage, and troubleshooting help |
| `tui` (or no command) | Open the dashboard |
| `--version` | Show installed version |
| `init` | Create the configuration and sample backlog |
| `validate` | Check backlog format and dependencies without calling a model |
| `check [--json]` | Audit local readiness without executing project commands or calling models |
| `runs [--status paused] [--json]` | Find saved runs; status filters also accept `unfinished` and `complete` |
| `doctor` | Validate the backlog and make a test call to the selected agent |
| `manage` | Start a new run |
| `status --run-id RUN_ID` | Show saved task status and usage |
| `report --run-id RUN_ID` | Print a JSON report |
| `report --run-id RUN_ID --html report.html` | Save an HTML report |
| `stop --run-id RUN_ID` | Request a pause after in-flight calls finish |
| `resume --run-id RUN_ID` | Continue a saved run |
| `retry --run-id RUN_ID --task BUG-001` | Allow a blocked task to try again; then use `resume` |
| `cleanup --run-id RUN_ID` | Remove run worktrees, keeping branches and logs |

Status, reports, stop, retry, and cleanup do not call a model. Reports are
snapshots; generate a new one to see updates. Retry and resume keep existing
usage counts.

## What happens during a run

Task Harbor plans up to four tasks at once, but implements them one at a time.
Each implementation gets a local checkpoint commit. Configured checks run first,
then a separate agent checks the acceptance criteria. Passing work is merged into
the integration branch, with code review every three passes by default.

A failed task gets two repair attempts in the same session. Further failures
trigger diagnosis and a fresh session, up to a configured limit.

Run state, plans, checks, and logs are saved under `.manager/runs/<run-id>/`.
Worktrees are stored beside your repository. Edit task requirements before
starting a new run; `resume` uses saved requirements, not later backlog edits.

Agents execute local commands. The permission settings and worktrees are not a
substitute for an isolated machine when working with untrusted code. After a hard
crash, stop any remaining agent processes before resuming.

## Development

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

Tests use simulated agent responses and real temporary Git repositories. CI runs
on Windows and Linux with Python 3.11 and 3.14. These tests do not establish live model quality or account compatibility; see
[EVALUATION.md](https://github.com/rhit-nayeems/task-harbor/blob/main/EVALUATION.md) for opt-in live evaluations.

- [Configuration and provider details](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/CONFIGURATION.md)
- [Architecture](https://github.com/rhit-nayeems/task-harbor/blob/main/ARCHITECTURE.md)
- [Workflow](https://github.com/rhit-nayeems/task-harbor/blob/main/WORKFLOW.md)
- [Evaluation](https://github.com/rhit-nayeems/task-harbor/blob/main/EVALUATION.md)
- [Changelog](https://github.com/rhit-nayeems/task-harbor/blob/main/CHANGELOG.md)
- [Technical status report](https://github.com/rhit-nayeems/task-harbor/blob/main/TECHNICAL_STATUS.md)

## Website

The landing page lives in [website/](https://github.com/rhit-nayeems/task-harbor/blob/main/website/README.md). It uses static HTML, CSS,
and JavaScript, with an interactive example workflow and installation guide.

## License

Task Harbor is available under the [MIT License](https://github.com/rhit-nayeems/task-harbor/blob/main/LICENSE).
