# Implemented workflow

```mermaid
flowchart TD
    START([IT Manager wakes]) --> ELIG[Compute eligible backlog items\nHard-check dependencies + acceptance criteria]
    ELIG --> MSEL[Opus Harbor chooses next planning batch\npriority is guidance, engineering judgment retained]
    MSEL --> PCAP{Planner slots available?\nmax 4}
    PCAP -- Yes --> PLAN[Parallel fresh Opus planners\nClaude Code plan mode]
    PCAP -- No --> WAIT[Wait for completed planner]
    WAIT --> PCAP

    PLAN --> PREVIEW[Fresh Opus manager plan review]
    PREVIEW -- REWORK --> PLAN
    PREVIEW -- APPROVED --> READY[READY]

    READY --> WT[Create isolated task worktree + local branch]
    WT --> IMPL[Opus implementer\nwrite-capable]
    IMPL --> CKPT[Harness checkpoint commit]
    CKPT --> QA[Fresh Opus QA\ndisposable worktree]
    QA --> QAV{QA verdict}

    QAV -- PASS --> MERGE[Merge into local integration branch]
    MERGE --> COUNT[Increment QA-pass counter]
    COUNT --> CRDUE{3 passes since review?}
    CRDUE -- No --> COMPLETE[COMPLETE]
    CRDUE -- Yes --> CR[Fresh Opus cumulative code review]
    CR --> CRV{Blocking/bug/critical finding?}
    CRV -- No --> RESET[Reset review counter]
    RESET --> COMPLETE
    CRV -- Yes --> CRFIX[Review-fix implementer]
    CRFIX --> CRQA[Independent QA recheck]
    CRQA --> CR2[Fresh re-review]
    CR2 --> CRV

    QAV -- FAIL/UNVERIFIED --> FC{Failures in current generation}
    FC -- 1 or 2 --> SAME[Resume SAME implementer session]
    SAME --> CKPT
    FC -- 3 --> CLASS[Opus Harbor classifies\nINVESTIGATOR vs AUDITOR]
    CLASS --> DIAG[Fresh diagnostic agent\nevidence only]
    DIAG --> PACKET[Harness creates CLEAN RESTART PACKET\nno previous conversation/strategy]
    PACKET --> FRESH[Fresh implementer session\nreset failure counter]
    FRESH --> CKPT

    COMPLETE --> START
```

## Intentional changes from the original sketch

1. **No startup planner deadlock.** Planner capacity is simply a hard maximum of four. When a slot exists and eligible work exists, the manager may fill it.
2. **Blocking is a condition, not a fake lifecycle state.** A task keeps its lifecycle status and gets a concrete blocked reason.
3. **Read-only independence is enforced by context/worktree boundaries, not only prose.** QA uses a disposable worktree; planning roles use Claude Code plan mode.
4. **The third-strike replacement gets evidence, not inherited reasoning.** The old session ID is retired.
5. **Code-review fixes explicitly go through QA recheck and then fresh re-review.**
6. **Autonomy is bounded.** Repeated clean restarts and review-fix loops have configurable safety ceilings so a pathological task cannot consume tokens forever.
7. **Write-capable task execution is serialized in v0.3.** This is a deliberate correctness choice. Parallel planners provide substantial throughput without introducing semantic branch-integration races. The worktree design supports a later conflict-aware parallel implementation scheduler.
8. **Approved plans are revalidated when integration advances.** Parallel planning remains useful, but an older plan is not handed to an implementer without a fresh manager judgment against the current integration state.
9. **Passes count only after merge.** A successful isolated QA verdict does not advance the periodic-review counter until the task branch is actually integrated; replay is idempotent per checkpoint.
10. **Interrupted transitions are recoverable.** Resume converts in-flight lifecycle states into the smallest safe repeatable action instead of pausing with "no executable transition."
