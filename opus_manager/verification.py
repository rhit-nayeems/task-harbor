"""Run operator-configured checks without a model; keep bounded output evidence."""
from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def run_checks(commands: list[str], cwd: Path, *, timeout: int, limit: int,
               env: dict[str, str] | None = None) -> list[dict]:
    results = []
    for command in commands:
        started = time.monotonic()
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(command, shell=True, cwd=cwd, env=env,
                                       stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=os.name != "nt")
            timed_out = False
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            size = output.tell()
            output.seek(max(0, size - limit))
            text = output.read().decode("utf-8", errors="replace")
        results.append({"command": command, "exit_code": process.returncode,
                        "timed_out": timed_out, "duration_seconds": round(time.monotonic() - started, 3),
                        "output": text, "output_truncated": size > limit})
        if timed_out or process.returncode != 0:
            break
    return results
