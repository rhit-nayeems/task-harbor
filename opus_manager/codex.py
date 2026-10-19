"""GPT coding agents through the authenticated Codex CLI JSONL interface."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from uuid import UUID

from .agent import AgentError, AgentResult
from .config import Config


def executable_command(binary: str) -> list[str]:
    resolved = shutil.which(binary) or binary
    if Path(resolved).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        # npm's Windows wrapper needs a shell. Invoke its JS entry point directly
        # so prompts and TOML values never pass through cmd.exe quoting.
        entry = Path(resolved).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        if not node or not entry.is_file():
            raise AgentError("Set codex_bin to a native Codex executable, or install Codex with npm and Node on PATH")
        return [node, str(entry)]
    return [resolved]


def parse_events(stdout: str, returncode: int, stderr: str = "", resume_session: str | None = None) -> AgentResult:
    session = resume_session
    final_text = None
    complete = False
    failures = []
    usage = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AgentError("Codex returned malformed JSONL") from exc
        if not isinstance(event, dict):
            raise AgentError("Codex returned a non-object event")
        kind = event.get("type")
        if kind == "thread.started":
            candidate = event.get("thread_id")
            try:
                UUID(candidate)
            except (ValueError, TypeError, AttributeError) as exc:
                raise AgentError("Codex returned an invalid thread ID") from exc
            if resume_session and candidate != resume_session:
                raise AgentError("Codex resumed a different thread than requested")
            session = candidate
        elif kind == "item.completed":
            item = event.get("item", {})
            if isinstance(item, dict) and item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                final_text = item["text"]
        elif kind == "turn.completed":
            complete = True
            reported_usage = event.get("usage") or {}
            if not isinstance(reported_usage, dict):
                raise AgentError("Codex returned malformed usage metadata")
            for key, value in reported_usage.items():
                if key.endswith("tokens") and type(value) is int and value >= 0:
                    usage[key] = usage.get(key, 0) + value
        elif kind == "turn.failed":
            failures.append(str(event.get("error", "Turn failed")))
        elif kind == "error":
            failures.append(str(event.get("message", "Codex error")))
    raw = {"provider": "codex", "session_id": session, "usage": usage}
    if returncode or failures or not complete or not session or not final_text:
        raise AgentError("Codex failed or returned an incomplete turn: " + "; ".join(failures + [stderr[-2000:]]), raw)
    return AgentResult(final_text, session, raw, returncode)


class CodexClient:
    def __init__(self, config: Config, hooks_dir: Path):
        self.config = config
        self.hooks_dir = hooks_dir

    def probe(self, cwd: Path) -> AgentResult:
        return self.run("Reply with the single word OK and nothing else.", cwd=cwd, role="analysis", max_turns=1)

    def run(self, prompt: str, *, cwd: Path, role: str, max_turns: int,
            resume_session: str | None = None, env: dict[str, str] | None = None,
            budget_usd: float | None = None) -> AgentResult:
        if role not in {"analysis", "read_only", "implementer"}:
            raise ValueError(f"Unknown agent role: {role}")
        if budget_usd is not None:
            raise AgentError("Codex does not support dollar caps; use call limits and agent_timeout_seconds")
        if resume_session:
            try:
                UUID(resume_session)
            except (ValueError, TypeError, AttributeError) as exc:
                raise AgentError("Invalid Codex resume session ID") from exc
        sandbox = "workspace-write" if role == "implementer" else "read-only"
        cmd = executable_command(self.config.codex_bin) + ["exec"]
        if resume_session:
            cmd.append("resume")
        cmd += ["--json", "--ignore-user-config", "--model", self.config.model,
                "-c", f"model_reasoning_effort={json.dumps(self.config.effort)}",
                "-c", 'approval_policy="never"',
                "-c", 'model_provider="openai"',
                "-c", f"sandbox_mode={json.dumps(sandbox)}",
                "-c", "sandbox_workspace_write.network_access=false"]
        if resume_session:
            cmd.append(resume_session)
        cmd.append("-")
        # max_turns is a Claude-specific control. Codex's bounded call uses the
        # process timeout; no undocumented turn-limit flag is invented here.
        instructions = ("Work only on the assigned task. Do not commit, push, create PRs, publish, deploy, "
                        "or modify BACKLOG.md or .manager/. The supervisor owns Git commits.\n\n")
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), input=instructions + prompt,
                                  text=True, encoding="utf-8", errors="replace", capture_output=True,
                                  timeout=self.config.agent_timeout_seconds, env=env)
        except FileNotFoundError as exc:
            raise AgentError(f"Codex CLI not found: {self.config.codex_bin}. Install Codex and run codex login.") from exc
        except subprocess.TimeoutExpired as exc:
            raise AgentError(f"Codex timed out after {self.config.agent_timeout_seconds}s") from exc
        return parse_events(proc.stdout, proc.returncode, proc.stderr, resume_session)
