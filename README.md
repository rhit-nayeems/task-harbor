# Task Harbor

Run a Markdown backlog with Claude Code or Codex. Task Harbor plans tasks,
implements them in Git worktrees, runs your checks, and collects the results
on a local branch for review. It does not push changes.

![Terminal dashboard with sample run data](https://raw.githubusercontent.com/rhit-nayeems/task-harbor/main/docs/terminal-dashboard.svg)

## Install

Requires Python 3.11+ and Git. To run agent tasks, install and sign in to
Claude Code or Codex.

```sh
python -m pip install task-harbor
```

Or use `pipx install task-harbor` for an isolated installation.
If the command isn't on PATH, use `python -m task_harbor` with the same arguments.
Upgrade with `python -m pip install --upgrade task-harbor` or `pipx upgrade task-harbor`.

## Quick start

Try a scripted bug fix first. No provider account or model calls are needed;
the demo creates a separate sample repository and runs real local tests:

```sh
task-harbor demo
```

From a Git repository with at least one commit and a configured Git author:

```sh
task-harbor setup
```

The wizard asks for your provider, model, test command, and call limit. It
requires verification and defaults to 20 calls per run. It creates
`.manager/config.json` and a sample `BACKLOG.md`, keeping any existing backlog.
Replace the sample with your tasks:

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

You can change these settings in `.manager/config.json`. For GPT, use
`"provider": "codex"` and set both dollar-budget fields to `null`.
See [configuration](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/CONFIGURATION.md)
for the fields and provider setup.

For example, add these settings for a Python project:

```json
{
  "verification_commands": ["python -m pytest"],
  "max_agent_calls": 100,
  "max_task_agent_calls": 20
}
```

Check the setup, then start:

```sh
task-harbor check
task-harbor manage
```

`check` reads local configuration without calling a model. `manage` starts agent
work and prints a run ID. Commit your project changes before starting; use
`task-harbor preflight --run-checks` to test your configured checks first.
`init` remains available for manual setup; its call limits default to unlimited.

Open the dashboard with `task-harbor`. It shows saved runs and task progress;
F1 opens help. Closing the dashboard does not stop a run.

## Review and resume

Replace `RUN_ID` with an ID from `task-harbor runs`:

```sh
task-harbor runs
task-harbor review --run-id RUN_ID --html review.html
task-harbor stop --run-id RUN_ID
task-harbor resume --run-id RUN_ID
```

The review report contains task evidence and verification results. Inspect the
changes on `manager/integration/RUN_ID` before merging into your own branch.
`stop` pauses after current calls finish; `resume` uses the saved task requirements.

Run `task-harbor guide` for setup help or `task-harbor --help` for all commands.
To work on another directory, put `--repo "path/to/project"` before the command.

Agents execute local commands. Git worktrees are not a security sandbox.

## Documentation

- [Configuration and providers](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/CONFIGURATION.md)
- [Checks, task agreements, and review](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/VERIFICATION.md)
- [Compare with a direct agent](https://github.com/rhit-nayeems/task-harbor/blob/main/EVALUATION.md)
- [Run a pilot](https://github.com/rhit-nayeems/task-harbor/blob/main/docs/PILOT.md)
- [Architecture](https://github.com/rhit-nayeems/task-harbor/blob/main/ARCHITECTURE.md) · [Technical status](https://github.com/rhit-nayeems/task-harbor/blob/main/TECHNICAL_STATUS.md) · [Changelog](https://github.com/rhit-nayeems/task-harbor/blob/main/CHANGELOG.md)

## Contributing

Bug reports, fixes, and documentation improvements are welcome.
See [CONTRIBUTING.md](https://github.com/rhit-nayeems/task-harbor/blob/main/CONTRIBUTING.md) for development setup and tests.

[MIT License](https://github.com/rhit-nayeems/task-harbor/blob/main/LICENSE)
