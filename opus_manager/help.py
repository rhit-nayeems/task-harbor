GUIDE = """TASK HARBOR — GETTING STARTED

1. Open a terminal in your Git repository (with at least one commit).
   task-harbor init
2. Edit BACKLOG.md: give each task an ID and acceptance criteria.
3. Edit .manager/config.json. Choose provider claude or codex and a model
   available to your account. Sign in with that provider's CLI first.
   For Codex, use a gpt-* model and leave both dollar caps null.
4. Set verification_commands to your test/build commands. Set max_agent_calls
   to limit usage; by default calls are unlimited.
5. Check and run:
   task-harbor preflight    (suggests checks; no model calls)
   task-harbor preflight --run-checks
   task-harbor validate
   task-harbor doctor       (makes a model call)
   task-harbor manage       (starts paid/subscription agent work)
6. Open another terminal in the same repository:
   task-harbor

MONITOR AND CONTROL
The dashboard refreshes every two seconds. Viewing does not call models.
Set up creates config/backlog; Validate checks them without model calls.
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
Compare against a direct agent with an operator-written task manifest:
   task-harbor compare --manifest comparison.json --output prepared
Preparation calls no models. Add --live with a new output folder to run both arms.

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
