import json
import subprocess
from pathlib import Path

from opus_manager.claude import ClaudeResult
from opus_manager.config import Config
from opus_manager.models import TaskStatus
from opus_manager.orchestrator import Orchestrator


class FakeClaude:
    def __init__(self):
        self.n = 0

    def _r(self, text):
        self.n += 1
        return ClaudeResult(text=text, session_id=f"s{self.n}", raw={}, returncode=0)

    def probe(self, cwd):
        return self._r("OK")

    def run(self, prompt, *, cwd, role, max_turns, resume_session=None, env=None):
        if "Choose up to" in prompt and "tasks to send" in prompt:
            ids = []
            data_start = prompt.find("Eligible candidates:")
            data = prompt[data_start:].split("Return ONLY JSON:", 1)[0]
            import re
            ids = re.findall(r'"id":\s*"([^"]+)"', data)
            return self._r(json.dumps({"task_ids": ids[:4], "reason": "priority"}))
        if "You are the planner" in prompt:
            return self._r("# Plan\nInspect, implement, and verify.\n\n## Acceptance mapping\nMap acceptance to tests.")
        if "IT Manager reviewing a planner" in prompt:
            return self._r(json.dumps({"verdict": "APPROVED", "feedback": "", "material_risks": []}))
        if "You are the implementer" in prompt and "approved plan" in prompt:
            task_id = json.loads(prompt.split("Task:\n",1)[1].split("\n\nApproved plan:",1)[0])["id"]
            (Path(cwd) / f"{task_id}.txt").write_text(f"implemented {task_id}\n")
            return self._r("implemented")
        if "independent QA agent" in prompt:
            return self._r(json.dumps({
                "verdict": "PASS", "summary": "verified",
                "acceptance": [{"criterion": "works", "status": "PASS", "evidence": "file present"}],
                "commands_run": [], "failures": [], "risks": []
            }))
        if "independent senior code reviewer" in prompt:
            return self._r(json.dumps({"verdict": "PASS", "findings": [], "summary": "clean"}))
        raise AssertionError(f"Unexpected prompt: {prompt[:200]}")


def init_repo(path: Path):
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("test\n", encoding="utf-8")
    (path / "BACKLOG.md").write_text("""# Backlog

## TASK-001 — One
- **Priority:** blocker
- **Status:** UNPLANNED
- **Owner:** —
- **Dependencies:** —
- **Blocked reason:** —
- **Plan:** —
- **Acceptance criteria:**
  - works
- **Next action:** plan

## TASK-002 — Two
- **Priority:** core
- **Status:** UNPLANNED
- **Owner:** —
- **Dependencies:** TASK-001
- **Blocked reason:** —
- **Plan:** —
- **Acceptance criteria:**
  - works
- **Next action:** plan

## TASK-003 — Three
- **Priority:** polish
- **Status:** UNPLANNED
- **Owner:** —
- **Dependencies:** TASK-002
- **Blocked reason:** —
- **Plan:** —
- **Acceptance criteria:**
  - works
- **Next action:** plan
""", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_full_three_task_flow_and_periodic_review(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo(repo)
    cfg = Config(qa_passes_per_code_review=3, keep_task_worktrees=False)
    manager = Orchestrator.start(repo, cfg)
    manager.claude = FakeClaude()
    manager.run()
    assert manager.state.stop_reason == "all tasks complete"
    assert all(t.status == TaskStatus.COMPLETE for t in manager.state.tasks.values())
    assert manager.state.qa_passes_since_review == 0
    integration = Path(manager.state.integration_worktree)
    assert (integration / "TASK-001.txt").exists()
    assert (integration / "TASK-002.txt").exists()
    assert (integration / "TASK-003.txt").exists()
    assert "COMPLETE" in (repo / "BACKLOG.md").read_text()


class EscalationClaude:
    def __init__(self):
        self.n = 0
        self.resume_ids = []

    def _r(self, text, sid=None):
        self.n += 1
        return ClaudeResult(text=text, session_id=sid or f"esc{self.n}", raw={}, returncode=0)

    def probe(self, cwd):
        return self._r("OK")

    def run(self, prompt, *, cwd, role, max_turns, resume_session=None, env=None):
        if resume_session:
            self.resume_ids.append(resume_session)
        if "Choose up to" in prompt and "tasks to send" in prompt:
            return self._r(json.dumps({"task_ids": ["TASK-001"], "reason": "only task"}))
        if "You are the planner" in prompt:
            return self._r("# Plan\nImplement correctly.\n\n## Acceptance mapping\nVerify behavior.")
        if "IT Manager reviewing a planner" in prompt:
            return self._r(json.dumps({"verdict": "APPROVED", "feedback": "", "material_risks": []}))
        if "You are the implementer" in prompt and "approved plan" in prompt:
            (Path(cwd) / "bad.txt").write_text("bad\n")
            return self._r("initial implementation", sid="poison-session")
        if "repair attempt" in prompt:
            return self._r("attempted repair", sid=resume_session)
        if "independent QA agent" in prompt:
            passed = (Path(cwd) / "good.txt").exists()
            return self._r(json.dumps({
                "verdict": "PASS" if passed else "FAIL",
                "summary": "good" if passed else "repro still fails",
                "acceptance": [{"criterion": "works", "status": "PASS" if passed else "FAIL", "evidence": "good.txt" if passed else "bad.txt"}],
                "commands_run": [],
                "failures": [] if passed else ["Expected good.txt; only bad.txt exists"],
                "risks": [],
            }))
        if "handling a third QA failure" in prompt:
            return self._r(json.dumps({"role": "INVESTIGATOR", "question": "Why is expected output absent?", "reason": "localized repro"}))
        if "independent investigator" in prompt:
            return self._r(json.dumps({
                "findings": ["bad.txt exists and expected good.txt is absent"],
                "scope": "localized",
                "neutral_failure_note": "Current implementation writes the wrong output artifact.",
                "uncertainties": [],
            }))
        if "fresh implementer taking over" in prompt:
            (Path(cwd) / "good.txt").write_text("good\n")
            return self._r("fresh implementation", sid="fresh-session")
        raise AssertionError(f"Unexpected prompt: {prompt[:240]}")


def test_three_strike_clean_restart_uses_fresh_session(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo(repo)
    # Keep only one task so periodic review is irrelevant.
    text = (repo / "BACKLOG.md").read_text(encoding="utf-8")
    text = text.split("## TASK-002", 1)[0].rstrip() + "\n"
    (repo / "BACKLOG.md").write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "single task"], cwd=repo, check=True, capture_output=True)

    cfg = Config(qa_passes_per_code_review=99, keep_task_worktrees=False)
    manager = Orchestrator.start(repo, cfg)
    fake = EscalationClaude()
    manager.claude = fake
    manager.run()
    task = manager.state.tasks["TASK-001"]
    assert task.status == TaskStatus.COMPLETE
    assert task.generation == 1
    assert task.implementer_session_id == "fresh-session"
    # First two fixes explicitly resume the original context; the fresh implementer does not.
    assert fake.resume_ids[:2] == ["poison-session", "poison-session"]
    assert "fresh-session" not in fake.resume_ids[:2]
    packets = list((manager.paths.diagnostics_dir).glob("*.restart_packet.md"))
    assert len(packets) == 1
    packet = packets[0].read_text()
    assert "Clean restart packet" in packet
    assert "prior implementer's conversation" in packet
