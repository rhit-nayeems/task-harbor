import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useCanvasLoop, useMotion, useReveal, useStage } from "@/components/harbor/motion";
import { GITHUB, INSTALL, ISSUES, InstallCommand, LICENSE, PULLS, PYPI, REQUIREMENTS } from "@/components/harbor/shared";

export const Route = createFileRoute("/combined")({
  head: () => ({
    meta: [
      { title: "Task Harbor — Run coding tasks. Review the evidence." },
      { name: "description", content: "Open-source Python CLI: a Markdown backlog run by Claude Code or Codex in isolated Git worktrees, checked, then held on a local branch for your review." },
      { property: "og:title", content: "Task Harbor — Run coding tasks. Review the evidence." },
      { property: "og:description", content: "Markdown backlog → isolated Git worktrees → checks before model QA → evidence on a local integration branch, awaiting your review." },
    ],
  }),
  component: Combined,
});
import { HarborPage, clamp, smooth, rgba, mix, BG, LINE, FG, MUTED, glyphOf, useStill, type RGB } from "@/components/harbor/page";


/* ── Scene 2: the workspace — backlog → worktrees → checks → model QA → review ── */
// Illustrative tasks. Same IDs and lane indices as the hero currents (glyphOf(lane, n)).
type Task = { id: string; title: string; diff: string[]; net: string; fail?: string };
const TASKS: Task[] = [
  { id: "T-101", title: "add retry to fetch client", diff: ["+ retries = 3", "- raise on first timeout"], net: "+1 −1" },
  { id: "T-102", title: "read config from TOML", diff: ["+ tomllib.load(fh)", "- json.load(fh)"], net: "+1 −1" },
  { id: "T-103", title: "fix date rounding", diff: ["+ round_to_minute(ts)", "- int(ts)"], net: "+1 −1", fail: "test_dst" },
  { id: "T-104", title: "document CLI usage", diff: ["+ ## Usage", "+ two examples"], net: "+2" },
];
const PASSING = TASKS.map((_, i) => i).filter((i) => !TASKS[i]!.fail);

// Scroll → stage position p ∈ [0,4]: overview, then one hold per layer, joined by short transitions.
const HOLDS: [number, number][] = [[0, 0.1], [0.22, 0.32], [0.44, 0.54], [0.66, 0.76], [0.88, 1]];
const stageOf = (s: number) => {
  for (let k = 0; k < 4; k++) {
    const [, e] = HOLDS[k]!, [n] = HOLDS[k + 1]!;
    if (s <= e) return k;
    if (s < n) return k + smooth(e, n, s);
  }
  return 4;
};
const HOLD_MID = HOLDS.map(([a, b]) => (a + b) / 2);
const LAYERS = ["Backlog", "Worktrees", "Checks & QA", "Review"];

/**
 * Exploded repository cross-section. Four open layers stacked in one shared axonometric camera:
 * backlog.md (top) → per-task worktree ribbons → verification stratum (checks, then model QA)
 * → local integration rail (bottom). The original branch is a separate vertical baseline that
 * only gives off worktrees; nothing returns to it. Selecting a layer opens the stack around it.
 */
function Workspace({ progress, header }: { progress: React.MutableRefObject<number>; header: React.RefObject<HTMLDivElement | null> }) {
  const still = useStill();
  const shown = useRef(0);
  const ref = useCanvasLoop((ctx, w, h, t) => {
    const mobile = w < 768;
    const tgt = progress.current;
    shown.current = still.current ? tgt : shown.current + (tgt - shown.current) * 0.14;
    if (Math.abs(tgt - shown.current) < 1e-4) shown.current = tgt;
    const p = stageOf(shown.current);
    const sel = [0, 1, 2, 3].map((i) => Math.max(0, 1 - Math.abs(p - (i + 1))));
    const ov = Math.max(0, 1 - p);
    // how strongly layer i is "above the current focus" (drawn as outline only so it never hides text)
    const above = (i: number) => sel.reduce((acc, s, j) => acc + (i < j ? s : 0), 0);

    // geometry (world units; x along the run, y up, z depth: + is far)
    const XW = mobile ? 2.7 : w > 1200 ? 7 : 5.5; // wider surfaces on wide screens so the stack uses the width
    const ZR = mobile ? 1.15 : 1.05;
    const D = 2.05 * ZR;
    const zRow = (i: number) => (1.5 - i) * ZR;
    const G = mobile ? 2.35 : 1.3, EA = mobile ? 0.7 : 0.6, EB = mobile ? 0.45 : 0.45; // layers above the focus turn to outline, so they need little clearance
    const yL = (i: number) => (1.5 - i) * G + sel.reduce((acc, s, j) => acc + (i < j ? s * EA : i > j ? -s * EB : 0), 0);

    // camera: one axonometric view for every stage
    const yaw = mobile ? -0.16 : -0.19, pitch = mobile ? 0.8 : 0.66;
    const cY = Math.cos(yaw), sY = Math.sin(yaw), cP = Math.cos(pitch), sP = Math.sin(pitch);
    const raw = (x: number, y: number, z: number) => {
      const x1 = x * cY - z * sY, z1 = x * sY + z * cY;
      return { x: x1, y: -(y * cP + z1 * sP) };
    };
    // fit the whole stack into the space under the header (no void, no clipping)
    const corners: { x: number; y: number }[] = [];
    for (let i = 0; i < 4; i++) for (const x of [-XW - 0.9, XW]) for (const z of [-D, D + 0.3]) corners.push(raw(x, yL(i), z));
    corners.push(raw(-XW - 0.9, yL(0) + 0.9, D + 0.3));
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const c of corners) { x0 = Math.min(x0, c.x); x1 = Math.max(x1, c.x); y0 = Math.min(y0, c.y); y1 = Math.max(y1, c.y); }
    const top = (header.current?.offsetHeight ?? 160) + (mobile ? 50 : 64); // room for the original-branch label
    const bottom = h - (mobile ? 92 : 96);
    const left = mobile ? 14 : Math.max(170, w * 0.14), right = mobile ? 14 : Math.max(60, w * 0.06);
    const S = Math.min((w - left - right) / (x1 - x0), (bottom - top) / (y1 - y0));
    const ox = left + ((w - left - right) - (x1 - x0) * S) / 2 - x0 * S;
    const oy = top + ((bottom - top) - (y1 - y0) * S) / 2 - y0 * S;
    const P = (x: number, y: number, z: number) => { const r = raw(x, y, z); return { x: ox + r.x * S, y: oy + r.y * S }; };
    const ex = P(1, 0, 0), eo = P(0, 0, 0);
    const ang = Math.atan2(ex.y - eo.y, ex.x - eo.x); // text is printed along each surface's run direction

    const base = mobile ? 11 : w > 1700 ? 14.5 : 13.5;
    ctx.globalAlpha = 1; ctx.fillStyle = rgba(BG); ctx.fillRect(0, 0, w, h);
    const font = (size: number, wt = 400, fam = '"JetBrains Mono", monospace') => `${wt} ${size.toFixed(1)}px ${fam}`;
    const text = (s: string, x: number, y: number, z: number, col: RGB, al: number, size = base, wt = 400, dy = 0, dx = 0, max = Infinity) => {
      if (al < 0.02) return;
      ctx.font = font(size, wt);
      if (ctx.measureText(s).width > max) { while (s.length > 4 && ctx.measureText(s + "…").width > max) s = s.slice(0, -1); s += "…"; }
      const q = P(x, y, z);
      ctx.save(); ctx.translate(q.x, q.y); ctx.rotate(ang);
      ctx.font = font(size, wt); ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.globalAlpha = Math.min(1, al); ctx.fillStyle = rgba(col); ctx.fillText(s, dx, dy);
      ctx.restore();
    };
    const line = (pts: [number, number, number][], al: number, lw = 1, col: RGB = LINE, dash: number[] = []) => {
      if (al < 0.02) return;
      ctx.globalAlpha = Math.min(1, al); ctx.strokeStyle = rgba(col); ctx.lineWidth = lw; ctx.setLineDash(dash);
      ctx.beginPath(); pts.forEach(([x, y, z], k) => { const q = P(x, y, z); if (k) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y); });
      ctx.stroke(); ctx.setLineDash([]);
    };
    /** Open surface: graphite fill lit from the back-left, a chamfered corner, silver front edges. */
    const surface = (xa: number, xb: number, za: number, zb: number, y: number, solid: number, lift: number, cut = 0.6, rules = 0) => {
      const poly: [number, number, number][] = [[xa, y, za], [xb, y, za], [xb, y, zb - cut], [xb - cut, y, zb], [xa, y, zb]];
      const q = poly.map(([x, yy, z]) => P(x, yy, z));
      if (solid > 0.02) {
        const g = ctx.createLinearGradient(q[4]!.x, q[4]!.y, q[1]!.x, q[1]!.y);
        g.addColorStop(0, `rgba(44,47,53,${0.96 * solid})`); g.addColorStop(1, `rgba(20,22,26,${0.96 * solid})`);
        ctx.save(); ctx.shadowColor = `rgba(0,0,0,${0.75 * solid})`; ctx.shadowBlur = 28; ctx.shadowOffsetY = 16;
        ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.beginPath(); q.forEach((c, k) => (k ? ctx.lineTo(c.x, c.y) : ctx.moveTo(c.x, c.y))); ctx.closePath(); ctx.fill();
        ctx.restore();
      }
      for (let r = 1; r <= rules; r++) { const z = za + ((zb - za) * r) / (rules + 1); line([[xa + 0.2, y, z], [xb - 0.2, y, z]], 0.07 * (0.4 + lift)); }
      line([[xa, y, zb], [xa, y, za], [xb, y, za], [xb, y, zb - cut]], 0.28 + 0.55 * lift, 1.1 + 0.4 * lift); // lit front edges
      line([[xb, y, zb - cut], [xb - cut, y, zb], [xa + 0.8, y, zb]], 0.1 + 0.15 * lift); // open back edge, stops short
    };
    const name = (i: number, al: number) => {
      const y = yL(i);
      if (mobile) { text(`0${i + 1} ${LAYERS[i]!.toUpperCase()}`, -XW, y, D + 0.42, FG, al, 10.5, 600); return; }
      const q = P(-XW - 0.35, y, -D);
      ctx.font = font(12, 600, '"Archivo", sans-serif'); ctx.textAlign = "right"; ctx.textBaseline = "middle";
      ctx.globalAlpha = al * 0.7; ctx.fillStyle = rgba(MUTED); ctx.fillText(`0${i + 1}`, q.x - 14, q.y - 16);
      ctx.font = font(15, 700, '"Archivo", sans-serif'); ctx.globalAlpha = al; ctx.fillStyle = rgba(FG); ctx.fillText(LAYERS[i]!.toUpperCase(), q.x - 14, q.y + 2);
    };
    const pulse = still.current ? -1 : (t * 0.16) % 1;

    // layer presentation weights
    const L = [0, 1, 2, 3].map((i) => {
      const up = clamp(above(i));
      const focus = sel[i]!;
      return { y: yL(i), solid: 1 - 0.9 * up, lift: Math.max(focus, ov * 0.55), txt: (1 - up) * Math.max(0.42, ov * 0.85, focus), detail: Math.max(focus, ov * 0.0) * (1 - up), up };
    });
    const X_C = mobile ? -0.55 : -XW * 0.1, X_Q = mobile ? 1.15 : XW * 0.4;
    const railZ = -D + (mobile ? (w < 360 ? 1.35 : 1.2) : 0.95); // room in front of the rail for its labels
    const railX = (j: number) => (mobile ? -0.9 : XW * 0.05) + j * (mobile ? 1.15 : 1.6);

    // original branch: a separate, stable baseline beside the stack. Only worktrees branch from it.
    const SX = -XW - 0.9, SZ = D + 0.3;
    const yTop = yL(0) + 0.9, yBot = yL(3) - 0.6;
    line([[SX, yTop, SZ], [SX, yBot, SZ]], 0.75, 2, LINE);
    const sTop = P(SX, yTop, SZ);
    ctx.save(); ctx.translate(sTop.x, sTop.y - 10); ctx.font = font(mobile ? 10 : 11.5, 500); ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    ctx.globalAlpha = 0.95; ctx.fillStyle = rgba(FG); ctx.fillText("original branch", 0, 0);
    const rv = Math.max(sel[3]!, ov);
    ctx.globalAlpha = 0.85 * rv; ctx.fillStyle = rgba(MUTED); ctx.fillText(mobile ? "unchanged · not merged" : "unchanged · nothing pushed or merged", 0, mobile ? 14 : 16);
    ctx.restore();

    // draw bottom → top so upper layers honestly occlude lower ones
    // ── 04 Review: local integration rail + evidence ledger
    {
      const l = L[3]!, y = l.y;
      surface(mobile ? -XW : -XW * 0.55, XW, -D, D, y, l.solid, l.lift, 0.7, 3);
      line([[mobile ? -XW + 0.2 : -XW * 0.55 + 0.2, y, railZ], [XW - 0.15, y, railZ]], 0.5 + 0.5 * l.lift, 2.4, FG);
      PASSING.forEach((ti, j) => {
        text(TASKS[ti]!.id, railX(j), y, railZ, FG, l.txt + 0.2, base, 700, -11);
      });
      const ra = l.detail;
      const lx = mobile ? -XW + 0.25 : -XW * 0.55 + 0.35;
      text("local integration branch", lx, y, railZ, MUTED, Math.max(ra, l.txt * 0.8), base * 0.9, 400, mobile ? (w < 360 ? 13 : 16) : 23);
      text("awaiting your review", lx, y, railZ, FG, ra, base * 1.05, 700, mobile ? (w < 360 ? 26 : 32) : 43);
      // ledger rows sit behind the rail, on the far half of the surface
      const LX = mobile ? -XW + 0.25 : XW * 0.05;
      const lz = (r: number) => D - 0.25 - r * (mobile ? (w < 360 ? 0.45 : 0.5) : 0.5);
      text("evidence", LX, y, lz(0), MUTED, ra, base * 0.85, 500);
      TASKS.forEach((task, r) => {
        const row = task.fail
          ? (mobile ? `${task.id}  ✗ test_dst · held` : `${task.id}  ${task.net}  ✗ ${task.fail}   held for repair`)
          : (mobile ? `${task.id}  ✓ checks  ✓ QA` : `${task.id}  ${task.net}  checks ✓   model QA ✓`);
        text(row, LX, y, lz(r + 1), task.fail ? FG : LINE, ra, base * 0.92, task.fail ? 600 : 400);
      });
      if (!mobile) text("full diffs · check output · QA notes · run state saved", LX, y, lz(4.9), MUTED, ra * 0.9, base * 0.8);
      name(3, Math.max(l.txt, 0.5) * (1 - l.up));
    }

    // ── 03 Checks & QA: verification stratum. Configured checks run first, model QA after.
    {
      const l = L[2]!, y = l.y;
      surface(-XW * (mobile ? 1 : 0.8), XW, -D, D, y, l.solid, l.lift, 0.6, 0);
      for (const [x, lab] of [[X_C, mobile ? "checks" : "configured checks"], [X_Q, mobile ? "then QA" : "then model QA"]] as [number, string][]) {
        line([[x, y, -D + 0.15], [x, y, D - 0.15]], 0.3 + 0.5 * l.lift, 1, LINE, [4, 4]);
        text(lab, x + 0.1, y, D - 0.25, MUTED, l.txt, base * 0.82, 500);
      }
      TASKS.forEach((task, i) => {
        const z = zRow(i) - 0.35;
        const x0 = -XW * (mobile ? 1 : 0.8) + 0.25;
        text(task.id, x0, y, z, FG, l.txt, base * 0.95, 700);
        const reach = task.fail ? X_C : XW - 0.3;
        line([[x0 + (mobile ? 1.05 : 1.0), y, z - 0.18], [reach, y, z - 0.18]], 0.25 + 0.3 * l.lift, 1);
        // a scan travelling the row: through checks first, then model QA (none past a failed check)
        if (pulse >= 0 && l.lift > 0.5) {
          const u = (pulse + i * 0.17) % 1, px = x0 + 1 + (reach - x0 - 1) * u;
          line([[px, y, z - 0.18], [Math.min(reach, px + 0.45), y, z - 0.18]], 0.9 * l.lift, 2, FG);
        }
        const r = l.detail, c = Math.max(l.txt * 0.75, r);
        if (task.fail) {
          text("✗ test_dst", X_C + 0.12, y, z, FG, Math.max(c, 0.6 * l.txt), base * 0.95, 700);
          ctx.font = font(base * 0.95, 700); const wF = ctx.measureText("✗ test_dst  ").width;
          text(mobile ? "· held" : "· held for repair", X_C + 0.12, y, z, MUTED, Math.max(r, l.txt * 0.6), base * 0.85, 500, 0, wF);
          line([[X_C, y, z - 0.18], [X_C + 1.2, y, z - 0.18]], 0.4 * l.txt, 1, LINE, [2, 4]);
        } else {
          text(mobile ? "✓" : "✓ pass", X_C + 0.12, y, z, LINE, c, base * 0.95, 500);
          text("✓", X_Q + 0.12, y, z, LINE, c, base * 0.95, 500);
          if (!mobile) text("notes", X_Q + 0.45, y, z, MUTED, r * 0.9, base * 0.8);
        }
      });
      name(2, Math.max(l.txt, 0.5) * (1 - l.up));
    }

    // identity threads: each task drops through the stack at its own row
    TASKS.forEach((task, i) => {
      const z = zRow(i) - 0.35;
      const a1 = 0.18 + 0.4 * Math.max(sel[1]!, sel[0]!), a2 = 0.18 + 0.4 * Math.max(sel[2]!, sel[1]!);
      line([[X_C, L[1]!.y, z], [X_C, L[2]!.y, z]], a2 * (1 - L[1]!.up), 1, LINE, [2, 4]);
      const j = PASSING.indexOf(i);
      if (j >= 0) line([[X_Q, L[2]!.y, z], [X_Q, (L[2]!.y + L[3]!.y) / 2, z], [railX(j) + 0.2, L[3]!.y + 0.05, railZ]], (0.18 + 0.45 * Math.max(sel[3]!, sel[2]! * 0.5)) * (1 - L[2]!.up), 1, LINE, [2, 4]);
      line([[-XW * 0.55, L[0]!.y, zRow(i) - 0.3], [-XW * 0.55, L[1]!.y, z]], a1 * (1 - L[0]!.up), 1, LINE, [2, 4]);
    });

    // ── 02 Worktrees: one ribbon per task, each branched from the original branch
    {
      const l = L[1]!, y = l.y;
      line([[-XW, y, -D], [XW, y, -D]], 0.15 + 0.2 * l.lift); // open ruled floor, no slab
      TASKS.forEach((task, i) => {
        const z = zRow(i) - 0.35;
        const xa = -XW + 0.1 + i * 0.12, xb = XW - (mobile ? 0.1 : 0.5) - i * 0.25;
        surface(xa, xb, z - 0.32, z + 0.32, y + i * 0.04, l.solid * 0.95, l.lift * 0.9, 0.25, 0);
        // branched from the original branch (one-way)
        line([[SX, y + 0.4, SZ], [SX + 0.5, y + 0.2, z + 0.1], [xa, y, z]], (0.3 + 0.4 * l.lift) * (1 - l.up), 1);
        text(task.id, xa + 0.2, y + i * 0.04, z, FG, l.txt, base, 700);
        const d = mobile ? task.diff[0]! : `${task.diff[0]}   ${task.diff[1]}`;
        ctx.font = font(base, 700); const wI = ctx.measureText(task.id + "  ").width;
        text(d, xa + 0.2, y + i * 0.04, z, LINE, Math.max(l.detail, ov * 0.5) * (1 - l.up), base * 0.9, 400, 0, wI, (xb - xa - 0.5) * S - wI);
        if (!mobile) text("own worktree", xb - 1.55, y + i * 0.04, z, MUTED, l.detail * 0.85, base * 0.78);
        if (pulse >= 0 && l.lift > 0.5) {
          const u = (pulse * 0.8 + i * 0.23) % 1, px = xa + 0.3 + (xb - xa - 0.6) * u;
          line([[px, y + i * 0.04, z - 0.32], [px + 0.5, y + i * 0.04, z - 0.32]], 0.8 * l.lift, 2, FG);
        }
      });
      name(1, Math.max(l.txt, 0.5) * (1 - l.up));
    }

    // ── 01 Backlog: backlog.md as a ruled manuscript page
    {
      const l = L[0]!, y = l.y;
      const xa = -XW, xb = mobile ? XW : XW * 0.5;
      surface(xa, xb, -D, D, y, l.solid, l.lift, 0.8, 0);
      text("backlog.md", xa + 0.3, y, D - 0.3, MUTED, Math.max(0.55, l.txt), base * 0.85, 500);
      TASKS.forEach((task, i) => {
        const z = zRow(i) - 0.3;
        line([[xa + 0.3, y, z - 0.22], [xb - 0.4, y, z - 0.22]], 0.12 + 0.12 * l.lift);
        // positions measured in pixels so ID, box and title never collide at any width
        ctx.font = font(base, 500); const wBox = ctx.measureText("- [ ] ").width;
        ctx.font = font(base, 700); const wId = ctx.measureText(task.id + "  ").width;
        const rowPx = Math.hypot(P(xb, y, z).x - P(xa, y, z).x, P(xb, y, z).y - P(xa, y, z).y) - 0.7 * S;
        text("- [ ]", xa + 0.3, y, z, MUTED, l.txt, base, 500);
        text(task.id, xa + 0.3, y, z, FG, l.txt, base, 700, 0, wBox);
        text(task.title, xa + 0.3, y, z, MUTED, mobile ? l.detail : Math.max(l.detail, ov * 0.7), mobile ? base * 0.9 : base, 400, 0, wBox + wId, rowPx - wBox - wId);
      });
      name(0, Math.max(l.txt, 0.5));
    }
    ctx.globalAlpha = 1; ctx.textAlign = "start";
  }, { dprCap: 2 });
  return <canvas ref={ref} aria-hidden className="absolute inset-0 h-full w-full" />;
}

const STEPS = [
  { t: "Overview", d: "One run as layers: backlog on top, review at the bottom. Your original branch stands apart." },
  { t: "Backlog", d: "Each line in a Markdown backlog is a task with its own ID." },
  { t: "Worktrees", d: "Claude Code or Codex works each task in a separate Git worktree, producing its own diff." },
  { t: "Checks & QA", d: "Your configured checks read each diff first; model QA follows. A failing check holds its task for repair." },
  { t: "Review", d: "Passing tasks gather on a local integration branch with their evidence, waiting for you. Nothing is pushed or merged." },
];

function Pipeline() {
  const section = useRef<HTMLElement>(null);
  const progress = useRef(0);
  const head = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);
  const { reduced } = useMotion();
  useEffect(() => {
    let raf = 0;
    const on = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const el = section.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        const s = clamp(-r.top / Math.max(1, r.height - window.innerHeight));
        progress.current = s;
        setStep(Math.round(stageOf(s)));
      });
    };
    on();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("scroll", on); window.removeEventListener("resize", on); };
  }, []);
  const go = (k: number) => {
    const el = section.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY + (el.offsetHeight - window.innerHeight) * HOLD_MID[k + 1]!;
    window.scrollTo({ top, behavior: reduced ? "auto" : "smooth" });
  };
  return (
    <section ref={section} aria-label="How a run works" className="relative h-[260svh] bg-mono-bg">
      <div className="sticky top-0 h-[100svh] overflow-hidden">
        <Workspace progress={progress} header={head} />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-48 md:h-40" style={{ background: "linear-gradient(to bottom, var(--mono-bg) 55%, transparent)" }} />
        <div ref={head} className="relative mx-auto max-w-6xl px-5 pt-6 md:px-10 md:pt-10">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="eyebrow text-mono-fg">How a run works</h2>
            <p className="eyebrow text-mono-muted">Illustrative run · example task IDs</p>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-[auto_minmax(0,1fr)] md:items-center md:gap-10">
            <nav aria-label="Run stages" className="grid grid-cols-4 border border-mono-line/20">
              {STEPS.slice(1).map((st, i) => (
                <button key={st.t} type="button" onClick={() => go(i)} aria-current={i + 1 === step ? "step" : undefined}
                  className={`eyebrow min-w-0 max-sm:text-[10px] max-sm:tracking-[0.04em] border-l border-mono-line/20 px-2 py-2.5 text-center transition-colors duration-300 ease-calm first:border-l-0 relative focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mono-fg focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-mono-bg sm:px-4 ${i + 1 === step ? "bg-mono-fg text-mono-bg" : "text-mono-muted hover:bg-mono-fg/10 hover:text-mono-fg"}`}>
                  <span className="hidden sm:inline">0{i + 1} </span>{st.t === "Checks & QA" ? <><span className="sm:hidden">Checks</span><span className="hidden sm:inline">Checks & QA</span></> : st.t}
                </button>
              ))}
            </nav>
            <div className="relative grid min-h-[3.25rem]" aria-live="polite">
              {STEPS.map((st, i) => (
                <p key={st.t} aria-hidden={i !== step}
                  className="col-start-1 row-start-1 max-w-xl text-[0.95rem] leading-snug text-mono-muted transition-opacity duration-500 ease-calm md:text-base"
                  style={{ opacity: i === step ? 1 : 0 }}>
                  {st.d}
                </p>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );

}
export function Combined() {
  return <HarborPage><Pipeline /></HarborPage>;
}

