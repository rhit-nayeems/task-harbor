import { Link, useLocation } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useMotion } from "./motion";

export const INSTALL = "python -m pip install task-harbor";
export const GITHUB = "https://github.com/rhit-nayeems/task-harbor";
export const PYPI = "https://pypi.org/project/task-harbor/";
export const ISSUES = `${GITHUB}/issues`;
export const PULLS = `${GITHUB}/pulls`;
export const LICENSE = `${GITHUB}/blob/main/LICENSE`;

/** Resolves true only after a write actually succeeds. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to legacy path */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch {
    return false;
  }
}

export const FACTS = [
  { k: "Backlog", v: "Tasks live in a Markdown backlog. Task Harbor runs them with Claude Code or Codex." },
  { k: "Isolation", v: "Each task runs in its own Git worktree." },
  { k: "Checks", v: "Your configured checks run before model QA." },
  { k: "Evidence", v: "Full diffs and evidence for every task. Run state is saved." },
  { k: "Integration", v: "Work lands on a local integration branch. Nothing is pushed or merged into your original branch automatically." },
];

export const REQUIREMENTS = "Python 3.11+ · Git · an authenticated provider";

export function InstallCommand({ tone = "dark" }: { tone?: "dark" | "paper" | "mono" }) {
  const [state, setState] = useState<"idle" | "ok" | "fail">("idle");
  const codeRef = useRef<HTMLElement>(null);
  return (
    <div
      className={`group flex w-full max-w-xl items-stretch border font-mono text-sm ${
        tone === "mono" ? "border-mono-line/30 bg-mono-surface text-mono-fg" : tone === "dark" ? "border-ivory/30 bg-forest-deep/70 backdrop-blur" : "border-forest-deep/30 bg-ivory"
      }`}
    >
      <span className={`flex items-center px-3 select-none ${tone === "mono" ? "text-mono-muted" : "text-signal"}`} aria-hidden>$</span>
      <code ref={codeRef} className="flex-1 select-all overflow-x-auto whitespace-nowrap py-3 pr-3">{INSTALL}</code>
      <button
        type="button"
        onClick={async () => {
          const ok = await copyText(INSTALL);
          setState(ok ? "ok" : "fail");
          if (!ok && codeRef.current) {
            const r = document.createRange();
            r.selectNodeContents(codeRef.current);
            const sel = window.getSelection();
            sel?.removeAllRanges();
            sel?.addRange(r);
          }
          window.setTimeout(() => setState("idle"), 2200);
        }}
        className="min-w-[5.5rem] border-l border-current/20 px-4 eyebrow focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring transition-colors hover:bg-primary hover:text-primary-foreground"
        aria-label="Copy install command"
      >
        <span aria-live="polite">{state === "ok" ? "Copied" : state === "fail" ? "Press ⌘/Ctrl+C" : "Copy"}</span>
      </button>
    </div>
  );
}

export function Links({ className = "" }: { className?: string }) {
  return (
    <div className={`flex gap-5 eyebrow ${className}`}>
      <a href={GITHUB} target="_blank" rel="noreferrer" className="underline decoration-1 underline-offset-4 hover:text-signal">GitHub ↗</a>
      <a href={PYPI} target="_blank" rel="noreferrer" className="underline decoration-1 underline-offset-4 hover:text-signal">PyPI ↗</a>
    </div>
  );
}

export function ConceptSwitcher() {
  const { pathname } = useLocation();
  const { paused, setPaused, reduced } = useMotion();
  const mono = pathname === "/combined";
  const items = [
    { to: "/a", label: "A", name: "ASCII Tides" },
    { to: "/b", label: "B", name: "Machine Room" },
    { to: "/c", label: "C", name: "Living Typeset" },
    { to: "/combined", label: "D", name: "Combined" },
  ] as const;
  return (
    <nav
      aria-label="Concept switcher"
      className={`fixed bottom-3 left-1/2 z-50 flex -translate-x-1/2 items-center gap-1 border p-1 font-mono text-[11px] shadow-2xl backdrop-blur-md ${mono ? "border-mono-line/25 bg-mono-surface/85 text-mono-fg" : "border-ivory/25 bg-forest-deep/85 text-ivory"}`}
    >
      {items.map((i) => {
        const active = pathname === i.to;
        return (
          <Link
            key={i.to}
            to={i.to}
            title={i.name}
            className={`flex items-center gap-2 px-3 py-2 uppercase tracking-widest transition-colors ${
              active ? (mono ? "bg-mono-fg text-mono-bg" : "bg-ivory text-forest-deep") : mono ? "hover:bg-mono-fg/10" : "hover:bg-ivory/10"
            }`}
          >
            <b>{i.label}</b>
            <span className="hidden sm:inline">{i.name}</span>
          </Link>
        );
      })}
      <button
        onClick={() => setPaused(!paused)}
        disabled={reduced}
        className={`ml-1 whitespace-nowrap border-l px-3 py-2 uppercase tracking-widest ${mono ? "border-mono-line/25 hover:bg-mono-fg/10" : "border-ivory/25 hover:bg-ivory/10"} disabled:opacity-50`}
        aria-pressed={paused}
        title={reduced ? "Reduced motion is on in your system settings" : undefined}
      >
        {reduced ? "Still" : paused ? "▶ Play" : "❚❚ Pause"}
      </button>
    </nav>
  );
}

export function Footer({ tone = "dark" }: { tone?: "dark" | "paper" | "mono" }) {
  return (
    <footer className={`flex flex-wrap items-center justify-between gap-4 border-t px-5 pb-24 pt-6 eyebrow md:px-10 ${tone === "paper" ? "text-forest-deep/70" : "text-ivory/60"}`}>
      <span>Task Harbor · open-source Python CLI</span>
      <Links />
    </footer>
  );
}


