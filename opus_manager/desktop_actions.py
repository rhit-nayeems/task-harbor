"""Launch existing CLI commands without a shell or a second terminal."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def launch_run(repo: Path, runs: Path, run_id: str | None = None):
    command = [sys.executable, "-m", "task_harbor", "--repo", str(repo)]
    command += ["resume", "--run-id", run_id] if run_id else ["manage"]
    logs = runs.parent / "launch-logs"
    logs.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    log = logs / f"{name}.log"
    options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with log.open("wb") as output:
        process = subprocess.Popen(command, cwd=repo, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, **options)
    return process, log
