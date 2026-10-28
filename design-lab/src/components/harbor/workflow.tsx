import { Link, useLocation } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMotion } from "./motion";

/* ── One shared illustrative run, used by every workflow variant ───────────── */
export type WTask = {
  id: string;
  title: string;
  file: string;
  diff: string[];
  stat: string;
  needs?: string;
  fail?: string;
};
export const WTASKS: WTask[] = [
  { id: "T-101", title: "add retry to fetch client", file: "src/fetch.py", diff: ["+ retries = 3", "- raise on first timeout"], stat: "+1 −1" },
  { id: "T-102", title: "read config from TOML", file: "src/config.py", diff: ["+ tomllib.load(fh)", "- json.load(fh)"], stat: "+1 −1" },
  { id: "T-103", title: "fix date rounding", file: "src/dates.py", diff: ["+ round_to_minute(ts)", "- int(ts)"], stat: "+1 −1", fail: "test_dst" },
  { id: "T-104", title: "document retry option", file: "docs/usage.md", diff: ["+ ## Retries", "+ --retries example"], stat: "+2", needs: "T-101" },
];

export const STAGES = [
  { t: "Backlog", d: "A Markdown backlog lists the tasks. T-104 depends on T-101." },
  { t: "Worktrees", d: "Tasks run one at a time, each in its own Git worktree with its own diff. T-104 waits for T-101." },
  { t: "Checks & QA", d: "Configured checks run first, then model QA. Passing work lands on the local integration branch; T-103 fails test_dst and is held." },
  { t: "Review", d: "Evidence and the local integration branch wait for your review. Original branch unchanged. Nothing pushed or merged." },
] as const;

export type Phase = "queued" | "waiting" | "implementing" | "worktree" | "checks" | "qa" | "landed" | "held";
export const PHASE_LABEL: Record<Phase, string> = {
  queued: "queued", waiting: "waits for T-101", implementing: "implementing", worktree: "diff ready",
  checks: "running checks", qa: "model QA", landed: "on integration", held: "held for repair",
};

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
/** Each stage plays its sequence over the first 70% of its scroll span, then holds a complete state. */
export const stageLocal = (s: number, k: number) => clamp((s - k) / 0.7);

/**
 * Phase of task i at stage position s ∈ [0,4]. Implementation is strictly one task at a time;
 * configured checks always precede model QA; T-104 starts only after T-101 lands on integration.
 */
export function phaseOf(i: number, s: number): Phase {
  const u1 = stageLocal(s, 1), u2 = stageLocal(s, 2);
  if (i === 3) {
    if (s < 1) return "queued";
    if (u2 < 0.55) return "waiting";
    if (u2 < 0.72) return "implementing";
    if (u2 < 0.84) return "checks";
    if (u2 < 0.94) return "qa";
    return "landed";
  }
  if (s < 1 || u1 < i / 3) return "queued";
  if (s < 2) return u1 < (i + 1) / 3 ? "implementing" : "worktree";
  const win = [[0, 0.12, 0.22], [0.22, 0.32, 0.42], [0.42, 0.55, 1]][i]!;
  if (u2 < win[0]!) return "worktree";
  if (u2 < win[1]!) return "checks";
  if (i === 2) return "held";
  if (u2 < win[2]!) return "qa";
  return "landed";
}
/** The single task in focus (mid-transition) or -1. */
export function activeTask(s: number) {
  for (let i = 0; i < 4; i++) { const p = phaseOf(i, s); if (p === "implementing" || p === "checks" || p === "qa") return i; }
  return -1;
}
/** Has task i reached a point where its diff exists? */
export const hasDiff = (p: Phase) => p !== "queued" && p !== "waiting";
export const checksDone = (p: Phase) => p === "qa" || p === "landed" || p === "held";

/* ── Shared section frame: scroll → stage, named stage controls, compare nav ── */
const VARIANTS = [
  { to: "/git-map", label: "Git map" },
  { to: "/terminal", label: "Living terminal" },
  { to: "/constellation", label: "Task constellation" },
] as const;

export const focusRing = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mono-fg focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-mono-bg";

export function WorkflowSection({ children, extra }: {
  children: (s: number, step: number, go: (k: number) => void) => ReactNode;
  /** Optional extra controls rendered beside pause (e.g. Replay). */
  extra?: ReactNode;
}) {
  const section = useRef<HTMLElement>(null);
  const [s, setS] = useState(0);
  const { reduced, paused, setPaused } = useMotion();
  const { pathname } = useLocation();
  useEffect(() => {
    let raf = 0;
    const on = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const el = section.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        setS(clamp(-r.top / Math.max(1, r.height - window.innerHeight)) * 4);
      });
    };
    on();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("scroll", on); window.removeEventListener("resize", on); };
  }, []);
  const step = Math.min(3, Math.floor(s));
  const go = (k: number) => {
    const el = section.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY + (el.offsetHeight - window.innerHeight) * (k === 0 ? 0 : Math.min(1, (k + 0.8) / 4));
    window.scrollTo({ top, behavior: reduced ? "auto" : "smooth" });
  };
  return (
    <section ref={section} id="workflow" aria-label="How a run works" className="relative h-[200svh] scroll-mt-0 bg-mono-bg">
      <div className="sticky top-0 flex h-[100svh] flex-col overflow-hidden">
        <div className="mx-auto w-full max-w-[90rem] px-4 pt-4 md:px-10 md:pt-7">
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <h2 className="eyebrow text-mono-fg">How a run works</h2>
            <nav aria-label="Compare workflow ideas" className="flex border border-mono-line/20 eyebrow max-sm:text-[10px]">
              {VARIANTS.map((v) => (
                <Link key={v.to} to={v.to} hash="workflow" aria-current={pathname === v.to ? "page" : undefined}
                  className={`relative border-l border-mono-line/20 px-2.5 py-1.5 first:border-l-0 focus-visible:z-10 ${focusRing} ${pathname === v.to ? "text-mono-fg underline decoration-1 underline-offset-4" : "text-mono-muted hover:text-mono-fg"}`}>
                  {v.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="mt-3 grid gap-3 md:mt-4 md:grid-cols-[auto_minmax(0,1fr)_auto] md:items-center md:gap-8">
            <nav aria-label="Run stages" className="grid grid-cols-4 border border-mono-line/20">
              {STAGES.map((st, i) => (
                <button key={st.t} type="button" onClick={() => go(i)} aria-current={i === step ? "step" : undefined}
                  className={`eyebrow relative min-w-0 border-l border-mono-line/20 px-2 py-2.5 text-center transition-colors duration-300 ease-calm first:border-l-0 focus-visible:z-10 max-sm:text-[10px] max-sm:tracking-[0.04em] sm:px-4 ${focusRing} ${i === step ? "bg-mono-fg text-mono-bg" : "text-mono-muted hover:bg-mono-fg/10 hover:text-mono-fg"}`}>
                  <span className="hidden sm:inline">0{i + 1} </span>{i === 2 ? <><span className="sm:hidden">Checks</span><span className="hidden sm:inline">{st.t}</span></> : st.t}
                </button>
              ))}
            </nav>
            <div className="grid min-h-[2.75rem]" aria-live="polite">
              {STAGES.map((st, i) => (
                <p key={st.t} aria-hidden={i !== step} className="col-start-1 row-start-1 max-w-2xl text-[0.9rem] leading-snug text-mono-muted transition-opacity duration-500 ease-calm md:text-[0.95rem]" style={{ opacity: i === step ? 1 : 0 }}>{st.d}</p>
              ))}
            </div>
            <div className="flex items-center gap-2 max-md:hidden">
              {extra}
              <button type="button" onClick={() => setPaused(!paused)} disabled={reduced} aria-pressed={paused}
                className={`eyebrow border border-mono-line/25 px-3 py-2 text-mono-muted hover:text-mono-fg disabled:opacity-50 ${focusRing}`}>
                {reduced ? "Still" : paused ? "Play" : "Pause"}
              </button>
            </div>
          </div>
        </div>
        <div className="relative mx-auto min-h-0 w-full max-w-[90rem] flex-1 px-4 pb-16 pt-3 md:px-10 md:pb-20">
          {children(s, step, go)}
          <p className="eyebrow pointer-events-none absolute bottom-[4.4rem] right-4 text-mono-muted/80 md:bottom-[5.2rem] md:right-10 max-md:hidden">Illustrative run · example task IDs</p>
        </div>
        <div className="flex items-center justify-between gap-2 px-4 pb-[4.25rem] md:hidden">
          <p className="eyebrow text-[10px] text-mono-muted">Illustrative run · example IDs</p>
          <div className="flex gap-2">
            {extra}
            <button type="button" onClick={() => setPaused(!paused)} disabled={reduced} aria-pressed={paused}
              className={`eyebrow border border-mono-line/25 px-3 py-2 text-[10px] text-mono-muted disabled:opacity-50 ${focusRing}`}>
              {reduced ? "Still" : paused ? "Play" : "Pause"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

