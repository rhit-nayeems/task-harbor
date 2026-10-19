from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .config import Config


# Backward-compatible imports for existing integrations.
from .agent import AgentError as ClaudeError, AgentResult as ClaudeResult


class ClaudeClient:
    def __init__(self, config: Config, hooks_dir: Path):
        self.config = config
        self.hooks_dir = hooks_dir

    def probe(self, cwd: Path) -> ClaudeResult:
        return self.run(
            "Reply with the single word OK and nothing else.",
            cwd=cwd,
            role="analysis",
            max_turns=1,
        )

    def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        role: str,
        max_turns: int,
        resume_session: str | None = None,
        env: dict[str, str] | None = None,
        budget_usd: float | None = None,
    ) -> ClaudeResult:
        cmd = [
            self.config.claude_bin,
            "-p",
            "--output-format", "json",
            "--model", self.config.model,
            "--effort", self.config.effort,
            "--max-turns", str(max_turns),
        ]
        if resume_session:
            cmd.extend(["--resume", resume_session])
        if budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(budget_usd)])

        # Read-only roles get inspection/test tools but no direct file editors.
        # They run in disposable or manager-owned worktrees when shell access is required.
        if role == "analysis":
            # Claude plan permissions constrain analysis; this is not an OS sandbox.
            cmd.extend(["--permission-mode", "plan"])
        elif role == "read_only":
            # Used only in disposable worktrees: shell access is useful for tests/repro,
            # while editor tools remain unavailable and all mutations are discarded.
            cmd.extend([
                "--allowedTools", "Read", "Glob", "Grep", "Bash",
                "--disallowedTools", "Edit", "Write", "NotebookEdit",
                "Bash(git commit:*)", "Bash(git push:*)", "Bash(gh pr create:*)", "Bash(gh repo:*)",
            ])
        elif role == "implementer":
            cmd.extend([
                "--permission-mode", "acceptEdits",
                "--allowedTools", "Read", "Glob", "Grep", "Edit", "Write", "NotebookEdit", "Bash",
                "--disallowedTools", "Bash(git commit:*)", "Bash(git push:*)", "Bash(gh pr create:*)", "Bash(gh repo:*)",
                "Bash(npm publish:*)", "Bash(pnpm publish:*)", "Bash(yarn publish:*)",
            ])
        else:
            raise ValueError(f"Unknown Claude role: {role}")

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self.config.agent_timeout_seconds,
                env=env,
            )
        except FileNotFoundError as e:
            raise ClaudeError(f"Claude CLI not found: {self.config.claude_bin}") from e
        except subprocess.TimeoutExpired as e:
            raise ClaudeError(f"Claude timed out after {self.config.agent_timeout_seconds}s") from e

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if not stdout:
            raise ClaudeError(f"Claude produced no output (exit {proc.returncode}): {stderr}")
        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise ClaudeError(f"Claude returned non-JSON wrapper output: {stdout[:1000]}\n{stderr}") from e

        text = raw.get("result")
        if not isinstance(text, str):
            # Be tolerant of evolving wrapper shapes while retaining raw data.
            text = raw.get("message") if isinstance(raw.get("message"), str) else stdout
        if proc.returncode != 0 or raw.get("is_error") is True:
            raise ClaudeError(f"Claude failed (exit {proc.returncode}): {text}\n{stderr}", raw)
        return ClaudeResult(
            text=text,
            session_id=raw.get("session_id"),
            raw=raw,
            returncode=proc.returncode,
        )


def extract_json(text: str) -> dict[str, Any]:
    """Extract a single JSON object from an agent response without trusting prose around it."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ClaudeError(f"Expected a JSON object from Claude, got: {text[:1500]}")
