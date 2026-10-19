from pathlib import Path

from .claude import ClaudeClient
from .codex import CodexClient
from .config import Config


def create_client(config: Config, hooks_dir: Path) -> ClaudeClient | CodexClient:
    if config.provider == "codex":
        return CodexClient(config, hooks_dir)
    return ClaudeClient(config, hooks_dir)
