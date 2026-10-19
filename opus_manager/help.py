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
   task-harbor validate
   task-harbor doctor       (makes a model call)
   task-harbor manage       (starts paid/subscription agent work)
6. Open another terminal in the same repository:
   task-harbor

MONITOR AND CONTROL
The dashboard reads local files every two seconds. It does not start agents.
Tab / Shift+Tab: change pane. Arrows: select task or run. F1: help. q: exit.
Closing the dashboard does not stop a run. Use:
   task-harbor stop --run-id RUN_ID
   task-harbor resume --run-id RUN_ID
Stop waits for in-flight calls to finish. Resume keeps existing usage counts.
Review results on manager/integration/RUN_ID. Nothing is automatically pushed.

TROUBLESHOOTING
Command not found? Use python -m task_harbor with the same arguments.
No runs? Start manage in another terminal; ensure both use the same repository.
Different directory? Put --repo "path/to/app" BEFORE the command.
Unknown cost? The provider did not report it; it is not a zero-cost call.
Blocked task? Inspect task details and saved logs, fix the cause, then use
retry --run-id RUN_ID --task TASK_ID followed by resume --run-id RUN_ID.

Run task-harbor COMMAND --help for command options.
Documentation: https://github.com/rhit-nayeems/task-harbor
"""
