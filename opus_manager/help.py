GUIDE = """TASK HARBOR — GETTING STARTED

Try task-harbor demo first: a separate sample repository, a scripted fix,
real tests, and an offline review report. No provider account or model calls.
For guided configuration in your own repository, run task-harbor setup.
It requires checks and defaults to a 20-call run limit.
For a new backlog, setup asks for your first task and acceptance criteria.
Use task-harbor add-task to add another task. Dashboard Set up has the same fields.

1. Open a terminal in your Git repository (with at least one commit).
   task-harbor setup
2. Enter your provider, model, checks, call limit, and first task when prompted.
   Sign in with the provider's CLI before running real work.
3. Commit project changes, then check and run:
   task-harbor check        (read-only readiness; no model calls or project commands)
   task-harbor preflight    (suggests checks; no model calls)
   task-harbor preflight --run-checks
   task-harbor validate
   task-harbor doctor       (makes a model call)
   task-harbor manage       (starts paid/subscription agent work)
4. Open another terminal in the same repository:
   task-harbor

For manual configuration, init creates a template. Edit BACKLOG.md and
.manager/config.json yourself. init has no call limit until you configure one.
For Codex, use a gpt-* model and leave both dollar caps null.

MONITOR AND CONTROL
List saved runs with task-harbor runs (or runs --status paused).
Use check --json and runs --json for machine-readable results.
Saved run status is a snapshot, not proof that a process is running.
The dashboard refreshes every two seconds. Viewing does not call models.
Set up collects configuration and tasks; Validate checks them without model calls.
New run and Resume show settings before you confirm agent work.
Stop pauses after in-flight calls. Launch output: .manager/launch-logs/.
Tab / Shift+Tab: change pane. Arrows: select task or run. F1: help. q: exit.
Closing the dashboard does not stop a run. Use:
   task-harbor stop --run-id RUN_ID
   task-harbor resume --run-id RUN_ID
Stop waits for in-flight calls to finish. Resume keeps existing usage counts.
Review results on manager/integration/RUN_ID. Nothing is automatically pushed.

EVIDENCE AND QUESTIONS
Press E in the dashboard to inspect a task, P for suggested checks.
   task-harbor review --run-id RUN_ID --html review.html
   task-harbor questions --run-id RUN_ID
   task-harbor answer --run-id RUN_ID --task TASK_ID --question Q-1 --text "Your answer"
   task-harbor resume --run-id RUN_ID
Record your review outcome separately from model QA:
   task-harbor feedback --run-id RUN_ID --task TASK_ID --outcome accepted --minutes 5
Add --supervision-minutes and --repair-minutes to measure total active effort.
Omitted values are unknown. Avoid counting the same minutes in multiple entries.
Compare against a direct agent with an operator-written task manifest:
   task-harbor compare --manifest comparison.json --output prepared
Preparation calls no models. Add --live with a new output folder to run both arms.
Record a comparison trial's human outcome with compare-feedback, then use
compare-report --experiment PATH (or --html comparison.html) to inspect both arms.
These commands call no providers. See EVALUATION.md for the full command examples.

TROUBLESHOOTING
Command not found? Use python -m task_harbor with the same arguments.
No runs? Use Set up, edit the files, Validate, then New run.
A run is one execution of a backlog; the picker only appears when runs exist.
Different directory? Put --repo "path/to/app" BEFORE the command.
Unknown cost? The provider did not report it; it is not a zero-cost call.
Blocked task? Inspect task details and saved logs, fix the cause, then use
retry --run-id RUN_ID --task TASK_ID followed by resume --run-id RUN_ID.

Run task-harbor COMMAND --help for command options.
Documentation: https://github.com/rhit-nayeems/task-harbor
"""
