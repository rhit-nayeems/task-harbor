from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backlog import parse_backlog, render_backlog
from .claude import ClaudeClient, extract_json
from .config import Config
from .gitops import (
    branch_exists,
    changed_paths,
    checkpoint,
    current_branch,
    detached_worktree_add,
    diff_range,
    ensure_local_exclude,
    ensure_repo,
    git,
    head,
    meaningful_dirty,
    matches_protected,
    merge_branch,
    remote_block_env,
    repo_snapshot,
    restore_paths,
    worktree_add,
    worktree_remove,
)
from .models import BacklogTask, ManagerState, PRIORITY_ORDER, TaskStatus
from .prompts import (
    classify_escalation,
    code_review,
    diagnose,
    fresh_implementer,
    implement,
    plan_rework,
    plan_review,
    planner,
    qa,
    review_fix,
    review_qa,
    same_implementer_fix,
    select_work,
)
from .state import append_event, load_state, save_state
from .usage import RunStopped, UsageLedger
from .verification import run_checks


class ManagerError(RuntimeError):
    pass


@dataclass
class Paths:
    repo: Path
    manager_root: Path
    run_dir: Path
    state_file: Path
    events_file: Path
    plans_dir: Path
    qa_dir: Path
    reviews_dir: Path
    diagnostics_dir: Path
    logs_dir: Path
    hooks_dir: Path
    lock_file: Path
    worktrees_root: Path


class Orchestrator:
    def __init__(self, repo: Path, config: Config, run_id: str, *, state: ManagerState | None = None):
        self.repo = repo.resolve()
        self.config = config
        manager_root = self.repo / config.manager_dir
        run_dir = manager_root / "runs" / run_id
        external_root = self.repo.parent / f".{self.repo.name}-opus-worktrees" / run_id
        self.paths = Paths(
            repo=self.repo,
            manager_root=manager_root,
            run_dir=run_dir,
            state_file=run_dir / "state.json",
            events_file=run_dir / "events.jsonl",
            plans_dir=run_dir / "plans",
            qa_dir=run_dir / "qa",
            reviews_dir=run_dir / "reviews",
            diagnostics_dir=run_dir / "diagnostics",
            logs_dir=run_dir / "logs",
            hooks_dir=run_dir / "hooks",
            lock_file=run_dir / "manager.lock",
            worktrees_root=external_root,
        )
        for p in [run_dir, self.paths.plans_dir, self.paths.qa_dir, self.paths.reviews_dir, self.paths.diagnostics_dir, self.paths.logs_dir]:
            p.mkdir(parents=True, exist_ok=True)
        self.state = state
        self.claude = ClaudeClient(config, self.paths.hooks_dir)
        self.agent_env = remote_block_env(self.paths.hooks_dir)
        self._persist_lock = threading.Lock()
        self._run_lock: Any | None = None
        self._resuming = False
        self.usage = UsageLedger(run_dir / "usage.json", config)

    @classmethod
    def start(cls, repo: Path, config: Config, backlog_path: Path | None = None) -> "Orchestrator":
        repo = repo.resolve()
        ensure_repo(repo)
        ensure_local_exclude(repo, config.manager_dir)
        dirty = meaningful_dirty(repo, config.manager_dir, config.backlog_file)
        if dirty and not config.allow_dirty_repo:
            raise ManagerError(
                "Repository has pre-existing changes outside manager-owned files. "
                "Commit/stash them or set allow_dirty_repo=true.\n" + "\n".join(dirty)
            )
        backlog = backlog_path or (repo / config.backlog_file)
        tasks = parse_backlog(backlog)
        validate_tasks(tasks)
        # A fresh manager run re-establishes runtime state from durable backlog intent.
        for t in tasks.values():
            if t.status == TaskStatus.COMPLETE:
                continue
            if t.plan_path and (repo / t.plan_path).exists():
                t.status = TaskStatus.PLAN_REVIEW
            else:
                t.status = TaskStatus.UNPLANNED
            t.owner = None
            t.blocked_reason = None
            t.qa_failures = 0
            t.generation = 0
            t.plan_reworks = 0
            t.checkpoint_commit = None
            t.last_qa_path = None
            t.metadata = {}

        now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"{now}_{head(repo)[:8]}"
        base_branch = current_branch(repo)
        base_commit = head(repo)
        integration_branch = f"{config.integration_branch_prefix}/{run_id}"
        external_root = repo.parent / f".{repo.name}-opus-worktrees" / run_id
        integration_path = external_root / "integration"
        if branch_exists(repo, integration_branch):
            raise ManagerError(f"Integration branch already exists: {integration_branch}")
        worktree_add(repo, integration_path, integration_branch, base_commit, create_branch=True)
        state = ManagerState(
            run_id=run_id,
            repo=str(repo),
            integration_branch=integration_branch,
            integration_worktree=str(integration_path),
            base_branch=base_branch,
            base_commit=base_commit,
            tasks=tasks,
            last_review_commit=base_commit,
        )
        obj = cls(repo, config, run_id, state=state)
        obj._sync_backlog(commit_integration=True)
        obj._event("RUN_STARTED", base_branch=base_branch, base_commit=base_commit, integration_branch=integration_branch)
        obj._persist()
        return obj

    @classmethod
    def resume(cls, repo: Path, config: Config, run_id: str) -> "Orchestrator":
        state_path = repo.resolve() / config.manager_dir / "runs" / run_id / "state.json"
        if not state_path.exists():
            raise ManagerError(f"Run not found: {run_id}")
        state = load_state(state_path)
        obj = cls(repo, config, run_id, state=state)
        obj._resuming = True
        return obj

    def _recover_interrupted_tasks(self) -> None:
        """Move in-flight states to explicit, idempotent recovery transitions.

        Claude invocations cannot be resumed until the harness knows whether the prior
        process returned. Durable checkpoint/session fields let the next manager turn
        repeat the smallest safe unit instead of deadlocking on a transient status.
        """
        assert self.state is not None
        self.state.active_planners = []
        recovered: list[dict[str, str]] = []
        for t in self.state.tasks.values():
            previous = t.status
            mode: str | None = None
            if previous == TaskStatus.PLANNING:
                t.status = TaskStatus.UNPLANNED
                t.owner = None
                t.next_action = "Restart planning after interruption"
            elif previous == TaskStatus.IMPLEMENTING:
                t.status = TaskStatus.READY
                t.owner = None
                mode = t.metadata.get("resume_mode", "implementation")
                t.next_action = "Resume implementation after interruption"
            elif previous == TaskStatus.QA:
                t.status = TaskStatus.READY
                t.owner = None
                mode = "qa" if t.checkpoint_commit else "implementation"
                t.next_action = "Repeat interrupted independent QA"
            elif previous == TaskStatus.QA_FAIL:
                t.status = TaskStatus.READY
                t.owner = None
                mode = "repair"
                t.next_action = "Resume repair from persisted QA evidence"
            elif previous == TaskStatus.QA_PASSED:
                t.status = TaskStatus.READY
                t.owner = None
                mode = "merge"
                t.next_action = "Resume merge of QA-passed checkpoint"
            if mode:
                t.metadata["resume_mode"] = mode
            if t.status != previous:
                recovered.append({"task_id": t.task_id, "from": previous.value, "to": t.status.value})
        if recovered:
            self._event("INTERRUPTED_TRANSITIONS_RECOVERED", tasks=recovered)

    def _persist(self) -> None:
        assert self.state is not None
        with self._persist_lock:
            save_state(self.paths.state_file, self.state)

    def _event(self, kind: str, **data: Any) -> None:
        assert self.state is not None
        with self._persist_lock:
            self.state.event_seq += 1
            event = {
                "seq": self.state.event_seq,
                "time": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                **data,
            }
            append_event(self.paths.events_file, event)
            save_state(self.paths.state_file, self.state)

    def _write_artifact(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def _sync_backlog(self, *, commit_integration: bool = False) -> None:
        assert self.state is not None
        # BACKLOG.md is manager-owned. Mirror state to the user's checkout and integration worktree.
        render_backlog(self.repo / self.config.backlog_file, self.state.tasks)
        integration = Path(self.state.integration_worktree)
        if integration.exists():
            render_backlog(integration / self.config.backlog_file, self.state.tasks)
            if commit_integration:
                checkpoint(integration, "manager: synchronize backlog state")

    def _call(self, prompt: str, **kwargs: Any):
        task_match = re.search(r'Task:\s*\{\s*"id":\s*"([^"\n]+)"', prompt)
        if task_match is None:
            task_match = re.search(r"# Clean restart packet [^\w]+ ([A-Za-z0-9_.-]+)", prompt)
        call_id, cap = self.usage.reserve(kwargs["role"], task_match.group(1) if task_match else None)
        if isinstance(self.claude, ClaudeClient):
            kwargs["budget_usd"] = cap
        try:
            result = self.claude.run(prompt, **kwargs)
        except BaseException as exc:
            self.usage.finish(call_id, getattr(exc, "raw", None), type(exc).__name__)
            raise
        self.usage.finish(call_id, result.raw)
        return result

    def probe(self) -> None:
        result = self.claude.probe(Path(self.state.integration_worktree))
        if result.text.strip().upper() != "OK":
            raise ManagerError(f"Claude probe returned unexpected response: {result.text}")
        self._event("CLAUDE_PROBE_OK")

    def run(self) -> None:
        self._acquire_run_lock()
        try:
            if self._resuming:
                self.state = load_state(self.paths.state_file)
                if not Path(self.state.integration_worktree).exists():
                    worktree_add(self.repo, Path(self.state.integration_worktree), self.state.integration_branch,
                                 self.state.integration_branch, create_branch=False)
                self._recover_interrupted_tasks()
                self.state.paused = False
                self.state.stop_reason = None
                (self.paths.run_dir / "stop-request.json").unlink(missing_ok=True)
                self._event("RUN_RESUMED")
            self._run_locked()
        except (RunStopped, KeyboardInterrupt) as exc:
            self.state.paused = True
            self.state.stop_reason = str(exc) or "Interrupted by operator"
            self._event("RUN_PAUSED", reason=self.state.stop_reason)
            self._sync_backlog()
        finally:
            self._release_run_lock()

    def _acquire_run_lock(self) -> None:
        self.paths.lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = self.paths.lock_file.open("a+b")
        if self.paths.lock_file.stat().st_size == 0:
            handle.write(b" ")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            handle.close()
            raise ManagerError(f"Run {self.state.run_id} is already active in another manager process") from e
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "run_id": self.state.run_id}).encode("utf-8"))
        handle.flush()
        self._run_lock = handle

    def _release_run_lock(self) -> None:
        handle = self._run_lock
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._run_lock = None

    def _run_locked(self) -> None:
        assert self.state is not None
        cycles = 0
        while not self.state.paused:
            if (self.paths.run_dir / "stop-request.json").exists():
                raise RunStopped("Operator requested a stop")
            cycles += 1
            if cycles > self.config.max_manager_cycles:
                self.state.paused = True
                self.state.stop_reason = "max_manager_cycles reached"
                self._event("RUN_PAUSED", reason=self.state.stop_reason)
                break

            self._refresh_blocking()
            if all(t.status == TaskStatus.COMPLETE for t in self.state.tasks.values()):
                if self.config.final_code_review and self.state.qa_passes_since_review:
                    if not self._run_code_review():
                        return
                self.state.stop_reason = "all tasks complete"
                self._sync_backlog(commit_integration=True)
                self._event("RUN_COMPLETE")
                self._persist()
                return

            progressed = False
            if self._plan_available_work():
                progressed = True

            self._refresh_blocking()
            reviewing = [t for t in self.state.tasks.values() if t.status == TaskStatus.CODE_REVIEW and not t.blocked]
            if reviewing:
                self._post_merge(reviewing[0])
                progressed = True
                if self.state.paused:
                    return

            ready = [t for t in self.state.tasks.values() if t.status == TaskStatus.READY and not t.blocked]
            ready.sort(key=lambda t: (PRIORITY_ORDER[t.priority], t.task_id))
            if ready:
                # Deliberately serialize write-capable implementation. Planners remain parallel.
                # This avoids hidden cross-task integration races while preserving safe task worktrees.
                if self._ensure_plan_current(ready[0]):
                    self._execute_task(ready[0])
                progressed = True

            if not progressed:
                actionable = [t for t in self.state.tasks.values() if t.status != TaskStatus.COMPLETE and not t.blocked]
                if actionable:
                    self.state.paused = True
                    self.state.stop_reason = "no executable transition for current state"
                else:
                    self.state.stop_reason = "no actionable work; remaining tasks are blocked"
                self._sync_backlog(commit_integration=True)
                self._event("RUN_STOPPED", reason=self.state.stop_reason)
                self._persist()
                return

    def _refresh_blocking(self) -> None:
        assert self.state is not None
        complete = {tid for tid, t in self.state.tasks.items() if t.status == TaskStatus.COMPLETE}
        for t in self.state.tasks.values():
            if t.status == TaskStatus.COMPLETE:
                t.blocked_reason = None
                t.metadata.pop("blocked_kind", None)
                continue
            missing = [d for d in t.dependencies if d not in complete]
            if missing:
                t.blocked_reason = "Waiting for dependencies: " + ", ".join(missing)
                t.metadata["blocked_kind"] = "dependency"
            elif not t.acceptance_criteria:
                t.blocked_reason = "Acceptance criteria are required before planning"
                t.metadata["blocked_kind"] = "acceptance"
            elif t.metadata.get("blocked_kind") in {"dependency", "acceptance"}:
                t.blocked_reason = None
                t.metadata.pop("blocked_kind", None)
        self._persist()

    def _planning_candidates(self) -> list[BacklogTask]:
        assert self.state is not None
        items = [t for t in self.state.tasks.values() if t.status in {TaskStatus.UNPLANNED, TaskStatus.PLAN_REVIEW} and not t.blocked]
        items.sort(key=lambda t: (PRIORITY_ORDER[t.priority], t.task_id))
        return items

    def _plan_available_work(self) -> bool:
        assert self.state is not None
        candidates = self._planning_candidates()
        if not candidates:
            return False
        slots = min(self.config.max_active_planners, len(candidates))
        # If there are existing plans awaiting review, review them first without spawning planners.
        existing = [t for t in candidates if t.status == TaskStatus.PLAN_REVIEW and t.plan_path]
        for t in existing:
            plan_file = self.repo / t.plan_path
            if not plan_file.exists():
                t.status = TaskStatus.UNPLANNED
                t.plan_path = None
                continue
            plan = plan_file.read_text(encoding="utf-8")
            self._review_plan(t, plan)
            return True

        candidates = [t for t in candidates if t.status == TaskStatus.UNPLANNED]
        if not candidates:
            return False
        completed = [tid for tid, t in self.state.tasks.items() if t.status == TaskStatus.COMPLETE]
        decision = {"task_ids": [t.task_id for t in candidates[:slots]], "reason": "priority and dependency order"}
        if self.config.scheduler == "model":
            result = self._call(
                select_work(candidates, slots, completed),
                cwd=Path(self.state.integration_worktree),
                role="analysis",
                max_turns=self.config.max_turns_manager,
                env=self.agent_env,
            )
            decision = extract_json(result.text)
        chosen = []
        seen = set()
        allowed = {t.task_id: t for t in candidates}
        for tid in decision.get("task_ids", []):
            if tid in allowed and tid not in seen and len(chosen) < slots:
                chosen.append(allowed[tid])
                seen.add(tid)
        if not chosen:
            # Deterministic safety fallback: manager cannot deadlock planning by returning malformed/empty selection.
            chosen = candidates[:slots]
        self._event("PLANNER_BATCH_SELECTED", task_ids=[t.task_id for t in chosen], rationale=decision.get("reason", ""))
        integration = Path(self.state.integration_worktree)
        snapshot = repo_snapshot(integration)
        for t in chosen:
            t.status = TaskStatus.PLANNING
            t.owner = f"planner:{t.task_id}"
            self.state.active_planners.append(t.task_id)
        self._sync_backlog()
        self._persist()

        plans: dict[str, str] = {}
        errors: dict[str, str] = {}
        stop_reason = None
        with ThreadPoolExecutor(max_workers=len(chosen)) as pool:
            futs = {
                pool.submit(
                    self._call,
                    planner(t, snapshot),
                    cwd=integration,
                    role="analysis",
                    max_turns=self.config.max_turns_planner,
                    env=self.agent_env,
                ): t
                for t in chosen
            }
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    plans[t.task_id] = fut.result().text
                except RunStopped as exc:
                    stop_reason = str(exc)
                    errors[t.task_id] = str(exc)
                except Exception as e:  # isolated agent failure; preserve other planner results
                    errors[t.task_id] = str(e)

        for t in chosen:
            if t.task_id in self.state.active_planners:
                self.state.active_planners.remove(t.task_id)
            if t.task_id in errors:
                t.status = TaskStatus.UNPLANNED
                t.owner = None
                t.last_error = errors[t.task_id]
                self._event("PLANNER_FAILED", task_id=t.task_id, error=errors[t.task_id])
                continue
            plan = plans[t.task_id]
            path = self.paths.plans_dir / f"{t.task_id}.md"
            self._write_artifact(path, plan)
            t.plan_path = str(path.relative_to(self.repo)) if path.is_relative_to(self.repo) else str(path)
            t.plan_base_commit = head(integration)
            t.status = TaskStatus.PLAN_REVIEW
            t.owner = "manager"
            self._event("PLAN_WRITTEN", task_id=t.task_id, path=str(path))
        self._sync_backlog()
        self._persist()
        if stop_reason:
            raise RunStopped(stop_reason)
        for t in chosen:
            if t.status == TaskStatus.PLAN_REVIEW:
                self._review_plan(t, self._task_plan(t))
        self._sync_backlog()
        self._persist()
        return True

    def _review_plan(self, t: BacklogTask, plan: str) -> None:
        assert self.state is not None
        integration = Path(self.state.integration_worktree)
        snapshot = repo_snapshot(integration)
        while True:
            result = self._call(
                plan_review(t, plan, snapshot),
                cwd=integration,
                role="analysis",
                max_turns=self.config.max_turns_manager,
                env=self.agent_env,
            )
            review = extract_json(result.text)
            verdict = str(review.get("verdict", "REWORK")).upper()
            review_path = self.paths.plans_dir / f"{t.task_id}.review.{t.plan_reworks}.json"
            self._write_artifact(review_path, json.dumps(review, indent=2))
            if verdict == "APPROVED":
                t.status = TaskStatus.READY
                t.owner = None
                t.next_action = "Implement approved plan"
                t.plan_base_commit = head(integration)
                t.plan_reworks = 0
                self._event("PLAN_APPROVED", task_id=t.task_id, review=str(review_path))
                return
            t.plan_reworks += 1
            if t.plan_reworks > self.config.max_plan_reworks:
                t.status = TaskStatus.UNPLANNED
                t.owner = None
                t.blocked_reason = "Plan rework limit reached; manager intervention required"
                t.metadata["blocked_kind"] = "plan_rework_limit"
                t.last_error = review.get("feedback", "Plan not approved")
                self._event("PLAN_REWORK_LIMIT", task_id=t.task_id, feedback=t.last_error)
                return
            revised = self._call(
                plan_rework(t, plan, review.get("feedback", "Address material review gaps.")),
                cwd=integration,
                role="analysis",
                max_turns=self.config.max_turns_planner,
                env=self.agent_env,
            )
            plan = revised.text
            path = self.paths.plans_dir / f"{t.task_id}.md"
            self._write_artifact(path, plan)
            self._event("PLAN_REWORKED", task_id=t.task_id, attempt=t.plan_reworks)

    def _ensure_plan_current(self, t: BacklogTask) -> bool:
        """Re-review an approved plan when integration advanced after planning."""
        assert self.state is not None
        integration = Path(self.state.integration_worktree)
        current = head(integration)
        if not t.plan_base_commit or t.plan_base_commit == current:
            return True
        source_changes = git(integration, "diff", "--name-only", t.plan_base_commit, current, "--", ".",
                             f":(exclude){self.config.backlog_file}", f":(exclude){self.config.manager_dir}/**").stdout
        if not source_changes:
            t.plan_base_commit = current
            self._persist()
            return True
        old_base = t.plan_base_commit
        t.status = TaskStatus.PLAN_REVIEW
        t.owner = "manager"
        t.next_action = "Revalidate plan against current integration branch"
        self._event("STALE_PLAN_REVIEW_STARTED", task_id=t.task_id, plan_base=old_base, current=current)
        self._review_plan(t, self._task_plan(t))
        return t.status == TaskStatus.READY

    def _task_plan(self, t: BacklogTask) -> str:
        if not t.plan_path:
            raise ManagerError(f"{t.task_id} has no approved plan")
        p = Path(t.plan_path)
        if not p.is_absolute():
            p = self.repo / p
        if not p.exists():
            # Current runs normally store plans under .manager/runs, which is absolute in state on some platforms.
            alt = self.paths.plans_dir / f"{t.task_id}.md"
            if alt.exists():
                p = alt
            else:
                raise ManagerError(f"Plan file missing for {t.task_id}: {t.plan_path}")
        return p.read_text(encoding="utf-8")

    def _prepare_task_worktree(self, t: BacklogTask) -> Path:
        assert self.state is not None
        if t.worktree_path and Path(t.worktree_path).exists():
            return Path(t.worktree_path)
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", t.task_id)
        branch = f"{self.config.task_branch_prefix}/{self.state.run_id}/{safe_id}-g{t.generation}"
        path = self.paths.worktrees_root / "tasks" / f"{safe_id}-g{t.generation}"
        start = head(Path(self.state.integration_worktree))
        if branch_exists(self.repo, branch):
            worktree_add(self.repo, path, branch, branch, create_branch=False)
        else:
            worktree_add(self.repo, path, branch, start, create_branch=True)
        t.worktree_path = str(path)
        t.branch_name = branch
        return path

    def _execute_task(self, t: BacklogTask) -> None:
        assert self.state is not None
        plan = self._task_plan(t)
        worktree = self._prepare_task_worktree(t)
        resume_mode = str(t.metadata.get("resume_mode", "implementation"))
        checkpoint_commit = t.checkpoint_commit

        if resume_mode == "merge" and checkpoint_commit:
            merged = self._merge_task(t, worktree, plan)
            if merged:
                self._count_qa_pass(t, t.checkpoint_commit or checkpoint_commit)
                self._post_merge(t)
            return

        if resume_mode == "qa" and checkpoint_commit:
            self._event("QA_RESTARTED_AFTER_INTERRUPTION", task_id=t.task_id, commit=checkpoint_commit)
        else:
            t.status = TaskStatus.IMPLEMENTING
            t.owner = f"implementer:{t.task_id}:g{t.generation}"
            self._sync_backlog()
            self._event("IMPLEMENTATION_STARTED", task_id=t.task_id, generation=t.generation, branch=t.branch_name, recovery=resume_mode)

            if resume_mode == "repair" and t.qa_failures > self.config.max_fix_attempts_before_restart:
                checkpoint_commit = self._clean_restart(t, worktree, plan, self._last_qa_evidence(t))
                t.checkpoint_commit = checkpoint_commit
                t.metadata["resume_mode"] = "qa"
                self._persist()
                return self._execute_task(t)
            if resume_mode == "repair" and t.implementer_session_id:
                evidence = self._last_qa_evidence(t)
                result = self._call(
                    same_implementer_fix(t, evidence, max(1, t.qa_failures)),
                    cwd=worktree,
                    role="implementer",
                    max_turns=self.config.max_turns_implementer,
                    resume_session=t.implementer_session_id,
                    env=self.agent_env,
                )
            elif t.implementer_session_id:
                result = self._call(
                    "Resume the assigned implementation after a manager interruption. Re-read the approved plan and current worktree, finish the task, validate it, and report what remains.",
                    cwd=worktree,
                    role="implementer",
                    max_turns=self.config.max_turns_implementer,
                    resume_session=t.implementer_session_id,
                    env=self.agent_env,
                )
            else:
                packet_path = t.metadata.get("restart_packet")
                initial_prompt = fresh_implementer(t, Path(packet_path).read_text(encoding="utf-8")) if resume_mode == "fresh" and packet_path else implement(t, plan)
                result = self._call(
                    initial_prompt,
                    cwd=worktree,
                    role="implementer",
                    max_turns=self.config.max_turns_implementer,
                    env=self.agent_env,
                )
                t.implementer_session_id = result.session_id
            self._write_artifact(self.paths.logs_dir / f"{t.task_id}.g{t.generation}.implement.md", result.text)
            self._guard_agent_changes(t, worktree)
            checkpoint_commit = checkpoint(worktree, f"manager checkpoint: {t.task_id} implementation g{t.generation}")
            t.checkpoint_commit = checkpoint_commit
            self._event("IMPLEMENTATION_CHECKPOINT", task_id=t.task_id, commit=checkpoint_commit, session=t.implementer_session_id)

        while True:
            assert checkpoint_commit is not None
            qa_result = self._run_qa(t, plan, checkpoint_commit)
            verdict = str(qa_result.get("verdict", "UNVERIFIED")).upper()
            if verdict == "PASS":
                t.status = TaskStatus.QA_PASSED
                t.owner = "manager"
                self._sync_backlog()
                self._event("QA_PASSED", task_id=t.task_id, commit=checkpoint_commit)
                merged = self._merge_task(t, worktree, plan)
                if not merged:
                    # _merge_task put the task back through repair/QA or paused it.
                    return
                self._count_qa_pass(t, t.checkpoint_commit or checkpoint_commit)
                self._post_merge(t)
                return

            t.status = TaskStatus.QA_FAIL
            t.qa_failures += 1
            evidence = json.dumps(qa_result, indent=2)
            self._event("QA_FAILED", task_id=t.task_id, verdict=verdict, failures=t.qa_failures)
            if t.qa_failures <= self.config.max_fix_attempts_before_restart:
                t.status = TaskStatus.IMPLEMENTING
                t.metadata["resume_mode"] = "repair"
                self._event("REPAIR_STARTED", task_id=t.task_id, attempt=t.qa_failures)
                fix = self._call(
                    same_implementer_fix(t, evidence, t.qa_failures),
                    cwd=worktree,
                    role="implementer",
                    max_turns=self.config.max_turns_implementer,
                    resume_session=t.implementer_session_id,
                    env=self.agent_env,
                )
                self._write_artifact(self.paths.logs_dir / f"{t.task_id}.g{t.generation}.fix{t.qa_failures}.md", fix.text)
                self._guard_agent_changes(t, worktree)
                checkpoint_commit = checkpoint(worktree, f"manager checkpoint: {t.task_id} repair {t.qa_failures}")
                t.checkpoint_commit = checkpoint_commit
                continue

            if t.generation + 1 >= self.config.max_fresh_implementer_generations:
                t.blocked_reason = "Repeated QA failures exceeded fresh-implementer generation limit"
                t.metadata["blocked_kind"] = "qa_generation_limit"
                t.owner = None
                self.state.paused = True
                self.state.stop_reason = f"{t.task_id} requires human escalation after repeated clean restarts"
                self._event("TASK_ESCALATED_TO_HUMAN", task_id=t.task_id, generations=t.generation + 1)
                self._sync_backlog()
                self._persist()
                return

            checkpoint_commit = self._clean_restart(t, worktree, plan, evidence)
            t.checkpoint_commit = checkpoint_commit

    def _last_qa_evidence(self, t: BacklogTask) -> str:
        if t.last_qa_path:
            path = Path(t.last_qa_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
        return json.dumps({
            "verdict": "UNVERIFIED",
            "summary": "The prior QA turn was interrupted or its artifact is unavailable. Re-inspect the current worktree and acceptance criteria.",
        }, indent=2)

    def _count_qa_pass(self, t: BacklogTask, commit: str) -> None:
        assert self.state is not None
        if t.metadata.get("counted_qa_commit") == commit:
            return
        self.state.qa_passes_since_review += 1
        t.metadata["counted_qa_commit"] = commit
        self._event("QA_PASS_COUNTED", task_id=t.task_id, commit=commit, pass_counter=self.state.qa_passes_since_review)

    def _guard_agent_changes(self, t: BacklogTask, worktree: Path) -> None:
        paths = changed_paths(worktree)
        violations = [p for p in paths if matches_protected(p, self.config.protected_paths, self.config.backlog_file)]
        if violations:
            restore_paths(worktree, violations)
            raise ManagerError(f"{t.task_id}: agent attempted to modify protected paths: {violations}")

    def _run_qa(self, t: BacklogTask, plan: str, commit: str) -> dict[str, Any]:
        assert self.state is not None
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", t.task_id)
        qa_path = self.paths.worktrees_root / "qa" / f"{safe_id}-{int(time.time() * 1000)}"
        detached_worktree_add(self.repo, qa_path, commit)
        try:
            t.metadata.pop("resume_mode", None)
            t.status = TaskStatus.QA
            t.owner = f"qa:{t.task_id}"
            t.checkpoint_commit = commit
            self._sync_backlog()
            self._event("QA_STARTED", task_id=t.task_id, commit=commit)
            checks = run_checks(self.config.verification_commands, qa_path,
                                timeout=self.config.verification_timeout_seconds,
                                limit=self.config.evidence_max_chars, env=self.agent_env)
            failed = any(c["exit_code"] != 0 or c["timed_out"] for c in checks)
            if failed:
                obj = {"verdict": "FAIL", "summary": "Configured verification failed before model QA",
                       "failures": [c for c in checks if c["exit_code"] != 0 or c["timed_out"]]}
            elif changed_paths(qa_path):
                obj = {"verdict": "UNVERIFIED", "summary": "Configured checks modified the verification worktree"}
            else:
                evidence = json.dumps(checks, indent=2)
                result = self._call(
                    qa(t, plan, []) + "\nHarness verification at this exact commit (do not repeat successful commands without a reason):\n" + evidence,
                    cwd=qa_path, role="read_only", max_turns=self.config.max_turns_qa, env=self.agent_env,
                )
                obj = extract_json(result.text)
                self._normalize_task_qa(t, obj)
            obj["harness_checks"] = checks
            obj["checkpoint_commit"] = commit
            # QA is disposable. Record if it mutated anything, but discard regardless.
            mutation = changed_paths(qa_path)
            if mutation:
                obj.setdefault("risks", []).append(f"QA agent mutated disposable worktree paths (discarded): {mutation}")
                if str(obj.get("verdict", "")).upper() == "PASS":
                    obj["verdict"] = "UNVERIFIED"
                    obj["summary"] = "QA mutated its supposedly read-only verification worktree; pass rejected."
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            artifact = self.paths.qa_dir / f"{t.task_id}.{stamp}.json"
            self._write_artifact(artifact, json.dumps(obj, indent=2))
            t.last_qa_path = str(artifact)
            return obj
        finally:
            worktree_remove(self.repo, qa_path, force=True)

    def _normalize_task_qa(self, t: BacklogTask, obj: dict[str, Any]) -> None:
        """Reject optimistic PASS wrappers that do not support every criterion."""
        verdict = str(obj.get("verdict", "UNVERIFIED")).upper()
        if verdict not in {"PASS", "FAIL", "UNVERIFIED"}:
            obj["verdict"] = "UNVERIFIED"
            obj["summary"] = f"QA returned unsupported verdict {verdict!r}."
            return
        obj["verdict"] = verdict
        if verdict != "PASS":
            return
        acceptance = obj.get("acceptance")
        expected = {f"AC-{i+1}": criterion for i, criterion in enumerate(t.acceptance_criteria)}
        seen = set()
        supported = isinstance(acceptance, list) and len(acceptance) == len(expected)
        for item in acceptance if isinstance(acceptance, list) else []:
            if not isinstance(item, dict):
                supported = False
                continue
            criterion_id = item.get("criterion_id")
            if criterion_id is None:
                matches = [key for key, text in expected.items() if text == item.get("criterion")]
                criterion_id = matches[0] if len(matches) == 1 else None
            if (not isinstance(criterion_id, str) or criterion_id not in expected or criterion_id in seen
                    or str(item.get("status", "")).upper() != "PASS"
                    or not isinstance(item.get("evidence"), str) or not item["evidence"].strip()):
                supported = False
            seen.add(criterion_id if isinstance(criterion_id, str) else None)
        supported = supported and seen == set(expected)
        if not supported:
            obj["verdict"] = "UNVERIFIED"
            obj["summary"] = "QA claimed PASS without PASS evidence for every acceptance criterion."
            obj.setdefault("failures", []).append("Acceptance evidence was missing, incomplete, or non-passing.")

    def _clean_restart(self, t: BacklogTask, worktree: Path, plan: str, evidence: str) -> str:
        assert self.state is not None
        if t.generation + 1 >= self.config.max_fresh_implementer_generations:
            t.blocked_reason = "Fresh-implementer generation limit reached"
            t.metadata["blocked_kind"] = "qa_generation_limit"
            raise RunStopped(f"{t.task_id}: {t.blocked_reason}")
        classification = extract_json(self._call(
            classify_escalation(t, evidence),
            cwd=worktree,
            role="analysis",
            max_turns=self.config.max_turns_manager,
            env=self.agent_env,
        ).text)
        role = str(classification.get("role", "INVESTIGATOR")).upper()
        if role not in {"INVESTIGATOR", "AUDITOR"}:
            role = "INVESTIGATOR"
        question = str(classification.get("question", "Establish the concrete cause and scope of the repeated QA failure."))
        diagnosis = extract_json(self._call(
            diagnose(t, role, question, evidence),
            cwd=worktree,
            role="analysis",
            max_turns=self.config.max_turns_diagnosis,
            env=self.agent_env,
        ).text)
        diag_path = self.paths.diagnostics_dir / f"{t.task_id}.g{t.generation}.{role.lower()}.json"
        self._write_artifact(diag_path, json.dumps({"classification": classification, "diagnosis": diagnosis}, indent=2))
        packet = self._restart_packet(t, plan, worktree, evidence, diagnosis)
        packet_path = self.paths.diagnostics_dir / f"{t.task_id}.g{t.generation}.restart_packet.md"
        self._write_artifact(packet_path, packet)
        self._event("CLEAN_RESTART_PACKET", task_id=t.task_id, role=role, path=str(packet_path))

        t.generation += 1
        t.qa_failures = 0
        t.implementer_session_id = None
        t.owner = f"implementer:{t.task_id}:g{t.generation}"
        t.status = TaskStatus.IMPLEMENTING
        t.metadata["resume_mode"] = "fresh"
        t.metadata["restart_packet"] = str(packet_path)
        self._event("FRESH_IMPLEMENTER_STARTING", task_id=t.task_id, generation=t.generation)
        # Keep code as evidence, but retire the previous conversation.
        result = self._call(
            fresh_implementer(t, packet),
            cwd=worktree,
            role="implementer",
            max_turns=self.config.max_turns_implementer,
            env=self.agent_env,
        )
        t.implementer_session_id = result.session_id
        self._write_artifact(self.paths.logs_dir / f"{t.task_id}.g{t.generation}.fresh_implement.md", result.text)
        self._guard_agent_changes(t, worktree)
        commit = checkpoint(worktree, f"manager checkpoint: {t.task_id} clean restart g{t.generation}")
        self._event("FRESH_IMPLEMENTER_STARTED", task_id=t.task_id, generation=t.generation, session=t.implementer_session_id)
        return commit

    def _restart_packet(self, t: BacklogTask, plan: str, worktree: Path, evidence: str, diagnosis: dict[str, Any]) -> str:
        return f"""# Clean restart packet — {t.task_id}\n\n## Original objective\n{t.title}\n\n## Approved plan\n{plan}\n\n## Acceptance criteria\n""" + "\n".join(f"- {c}" for c in t.acceptance_criteria) + f"""\n\n## Current repository state\n```text\n{repo_snapshot(worktree)}\n```\n\n## Concrete failure evidence\n```json\n{evidence}\n```\n\n## Independent diagnostic evidence\n```json\n{json.dumps(diagnosis, indent=2)}\n```\n\n## Neutral failure note\n{diagnosis.get('neutral_failure_note', 'Repeated QA evidence indicates the current implementation does not yet satisfy verification.')}\n\nThis packet intentionally omits the prior implementer's conversation and solution strategy. Evidence is context, not an instruction to preserve the previous approach.\n"""

    def _merge_task(self, t: BacklogTask, worktree: Path, plan: str) -> bool:
        assert self.state is not None
        integration = Path(self.state.integration_worktree)
        ok, detail = merge_branch(integration, t.branch_name or "", t.task_id)
        if ok:
            t.completed_commit = detail
            self._event("TASK_MERGED", task_id=t.task_id, integration_commit=detail)
            return True

        # Integration moved since this task branched and a real conflict exists. Put latest integration into
        # the task worktree and let the same implementer resolve with context, then QA again.
        self._event("MERGE_CONFLICT", task_id=t.task_id, detail=detail)
        merge = git(worktree, "merge", self.state.integration_branch, check=False, timeout=300)
        conflict_paths = git(worktree, "diff", "--name-only", "--diff-filter=U", check=False).stdout
        evidence = json.dumps({
            "verdict": "FAIL",
            "summary": "Task passed isolated QA but conflicts with the current integration branch.",
            "failures": [f"Merge conflict paths: {conflict_paths or detail}"],
        }, indent=2)
        if merge.code == 0:
            checkpoint_commit = head(worktree)
        else:
            t.qa_failures += 1
            if t.qa_failures > self.config.max_fix_attempts_before_restart:
                # Integration conflicts can poison assumptions too; use the same clean-restart policy.
                checkpoint_commit = self._clean_restart(t, worktree, plan, evidence)
            else:
                fix = self._call(
                    same_implementer_fix(t, evidence, t.qa_failures),
                    cwd=worktree,
                    role="implementer",
                    max_turns=self.config.max_turns_implementer,
                    resume_session=t.implementer_session_id,
                    env=self.agent_env,
                )
                self._write_artifact(self.paths.logs_dir / f"{t.task_id}.merge_fix{t.qa_failures}.md", fix.text)
                self._guard_agent_changes(t, worktree)
                checkpoint_commit = checkpoint(worktree, f"manager checkpoint: {t.task_id} integration conflict repair")
        t.checkpoint_commit = checkpoint_commit
        qa_result = self._run_qa(t, plan, checkpoint_commit)
        if str(qa_result.get("verdict", "")).upper() != "PASS":
            # Re-enter the normal execution loop with the concrete recheck evidence.
            t.qa_failures += 1
            t.status = TaskStatus.READY
            t.owner = None
            t.metadata["resume_mode"] = "repair"
            t.next_action = "Re-run implementation/repair after integration recheck failure"
            self._event("INTEGRATION_RECHECK_FAILED", task_id=t.task_id, qa=qa_result)
            return False
        ok2, detail2 = merge_branch(integration, t.branch_name or "", t.task_id)
        if not ok2:
            t.blocked_reason = f"Repeated integration conflict requires manager intervention: {detail2}"
            t.metadata["blocked_kind"] = "integration_conflict"
            self.state.paused = True
            self.state.stop_reason = f"Integration conflict on {t.task_id}"
            self._event("INTEGRATION_CONFLICT_ESCALATED", task_id=t.task_id, detail=detail2)
            return False
        t.completed_commit = detail2
        self._event("TASK_MERGED", task_id=t.task_id, integration_commit=detail2)
        return True

    def _post_merge(self, t: BacklogTask) -> None:
        assert self.state is not None
        if self.state.qa_passes_since_review >= self.config.qa_passes_per_code_review:
            t.status = TaskStatus.CODE_REVIEW
            self._sync_backlog(commit_integration=True)
            if not self._run_code_review():
                return
        t.status = TaskStatus.COMPLETE
        t.owner = None
        t.next_action = "Complete"
        t.blocked_reason = None
        self._sync_backlog(commit_integration=True)
        self._event("TASK_COMPLETE", task_id=t.task_id, commit=t.completed_commit)
        if not self.config.keep_task_worktrees and t.worktree_path:
            worktree_remove(self.repo, Path(t.worktree_path), force=True)

    def _run_code_review(self) -> bool:
        assert self.state is not None
        integration = Path(self.state.integration_worktree)
        base = self.state.last_review_commit or self.state.base_commit
        current = head(integration)
        batch = [tid for tid, task in self.state.tasks.items() if task.completed_commit and git(integration, "merge-base", "--is-ancestor", base, task.completed_commit, check=False).code == 0]
        diff = diff_range(integration, base, current)
        review_obj = extract_json(self._call(
            code_review(batch, base, diff[:self.config.evidence_max_chars]),
            cwd=integration,
            role="analysis",
            max_turns=self.config.max_turns_reviewer,
            env=self.agent_env,
        ).text)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        review_path = self.paths.reviews_dir / f"code_review_{stamp}.json"
        self._write_artifact(review_path, json.dumps(review_obj, indent=2))
        self._event("CODE_REVIEW_PROVIDED", verdict=review_obj.get("verdict"), path=str(review_path))
        if not self._review_requires_changes(review_obj):
            self.state.last_review_commit = current
            self.state.qa_passes_since_review = 0
            self._event("CODE_REVIEW_COMPLETED", commit=current)
            return True

        if not self._fix_code_review(review_obj):
            return False
        self.state.last_review_commit = head(integration)
        self.state.qa_passes_since_review = 0
        self._event("CODE_REVIEW_COMPLETED", commit=self.state.last_review_commit)
        return True

    def _review_requires_changes(self, review_obj: dict[str, Any]) -> bool:
        verdict = str(review_obj.get("verdict", "CHANGES_REQUIRED")).upper()
        findings = review_obj.get("findings", [])
        if not isinstance(findings, list):
            return True
        blocking = any(
            isinstance(finding, dict)
            and str(finding.get("severity", "")).upper() in {"BLOCKER", "BUG", "CRITICAL"}
            for finding in findings
        )
        return verdict != "PASS" or blocking

    def _fix_code_review(self, review_obj: dict[str, Any]) -> bool:
        assert self.state is not None
        integration = Path(self.state.integration_worktree)
        safe = f"review-fix-{self.state.event_seq}"
        branch = f"{self.config.task_branch_prefix}/{self.state.run_id}/{safe}"
        worktree = self.paths.worktrees_root / "review-fixes" / safe
        worktree_add(self.repo, worktree, branch, head(integration), create_branch=True)
        session: str | None = None
        payload = json.dumps(review_obj, indent=2)
        try:
            for attempt in range(self.config.max_code_review_fix_attempts + 1):
                if attempt == 0:
                    result = self._call(
                        review_fix(payload), cwd=worktree, role="implementer",
                        max_turns=self.config.max_turns_implementer, env=self.agent_env,
                    )
                    session = result.session_id
                else:
                    result = self._call(
                        review_fix(payload),
                        cwd=worktree, role="implementer", max_turns=self.config.max_turns_implementer,
                        resume_session=session, env=self.agent_env,
                    )
                violations = [p for p in changed_paths(worktree) if matches_protected(p, self.config.protected_paths, self.config.backlog_file)]
                if violations:
                    restore_paths(worktree, violations)
                    raise ManagerError(f"Code-review fixer modified protected paths: {violations}")
                commit = checkpoint(worktree, f"manager checkpoint: cumulative code review fix {attempt + 1}")
                qa_path = self.paths.worktrees_root / "qa" / f"review-{int(time.time()*1000)}"
                detached_worktree_add(self.repo, qa_path, commit)
                try:
                    qa_obj = extract_json(self._call(
                        review_qa(payload, self.config.verification_commands),
                        cwd=qa_path, role="read_only", max_turns=self.config.max_turns_qa, env=self.agent_env,
                    ).text)
                    mutation = changed_paths(qa_path)
                    if mutation:
                        qa_obj.setdefault("failures", []).append(f"Review QA mutated disposable paths: {mutation}")
                        qa_obj["verdict"] = "UNVERIFIED"
                        qa_obj["summary"] = "Review QA mutated its disposable worktree; verdict rejected."
                finally:
                    worktree_remove(self.repo, qa_path, force=True)
                self._write_artifact(self.paths.reviews_dir / f"review_fix_qa_{attempt}.json", json.dumps(qa_obj, indent=2))
                if str(qa_obj.get("verdict", "")).upper() != "PASS":
                    payload += "\n\nLatest QA evidence:\n" + json.dumps(qa_obj, indent=2)
                    continue
                ok, detail = merge_branch(integration, branch, "CODE_REVIEW_FIX")
                if not ok:
                    payload += f"\n\nIntegration merge conflict after fix: {detail}"
                    continue
                # Re-review after QA recheck, matching the intended REVIEW_PROVIDED -> FIX -> QA_RECHECK -> review loop.
                base = self.state.last_review_commit or self.state.base_commit
                rereview = extract_json(self._call(
                    code_review([], base, diff_range(integration, base, head(integration))[:self.config.evidence_max_chars]),
                    cwd=integration, role="analysis", max_turns=self.config.max_turns_reviewer, env=self.agent_env,
                ).text)
                self._write_artifact(self.paths.reviews_dir / f"review_rereview_{attempt}.json", json.dumps(rereview, indent=2))
                if not self._review_requires_changes(rereview):
                    return True
                payload = json.dumps(rereview, indent=2)
            self.state.paused = True
            self.state.stop_reason = "Cumulative code-review fixes exceeded bounded retry limit"
            self._event("CODE_REVIEW_ESCALATED", reason=self.state.stop_reason)
            return False
        finally:
            if not self.config.keep_task_worktrees:
                worktree_remove(self.repo, worktree, force=True)


def validate_tasks(tasks: dict[str, BacklogTask]) -> None:
    errors: list[str] = []
    for tid, t in tasks.items():
        for dep in t.dependencies:
            if dep not in tasks:
                errors.append(f"{tid}: unknown dependency {dep}")
        if tid in t.dependencies:
            errors.append(f"{tid}: task cannot depend on itself")
    # DFS cycle detection
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(tid: str, stack: list[str]) -> None:
        if tid in visited:
            return
        if tid in visiting:
            cycle = stack[stack.index(tid):] + [tid] if tid in stack else stack + [tid]
            errors.append("dependency cycle: " + " -> ".join(cycle))
            return
        visiting.add(tid)
        stack.append(tid)
        for dep in tasks[tid].dependencies:
            if dep in tasks:
                visit(dep, stack)
        stack.pop()
        visiting.remove(tid)
        visited.add(tid)
    for tid in tasks:
        visit(tid, [])
    if errors:
        raise ManagerError("Invalid backlog:\n- " + "\n- ".join(errors))
