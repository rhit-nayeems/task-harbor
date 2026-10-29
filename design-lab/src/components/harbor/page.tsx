import { SiteHeader, EngineeringTeam, ReviewSection, GettingStarted, SiteClosing } from '../../site';
import { useEffect, useRef, useState, type ReactNode } from "react";
import { MOTION_SPEED, useCanvasLoop, useMotion, useReveal, useStage } from "@/components/harbor/motion";
import { GITHUB, INSTALL, ISSUES, InstallCommand, LICENSE, PULLS, PYPI, REQUIREMENTS } from "@/components/harbor/shared";

/**
 * Shared /combined page shell: full-hero ASCII harbor, editorial and install sections.
 * Workflow variants (/combined, /git-map, /terminal, /constellation) pass their section as children.
 */
/* ── shared math, timing and identity ─────────────────────────────── */
export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const smooth = (a: number, b: number, v: number) => { const x = clamp((v - a) / (b - a)); return x * x * (3 - 2 * x); };
export const LANES = 4; // one lane per illustrative task (T-101…T-104)
export const FLOW = 0.03; // one shared flow speed (lane cycles per second), always left → right
export const TASK_GLYPHS = "-[]#*:=+>_";
/** Stable glyph identity per lane slot, shared by hero and machine. */
export const glyphOf = (l: number, n: number) => TASK_GLYPHS.charAt((l * 7 + n) % TASK_GLYPHS.length);

export type RGB = [number, number, number];
// Canvas mirrors of the --mono-* tokens in styles.css (canvas needs numeric channels).
export const BG: RGB = [11, 12, 14], LINE: RGB = [198, 203, 210], FG: RGB = [243, 243, 241], MUTED: RGB = [165, 168, 174];
export const rgba = (c: RGB, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
export const mix = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

export function useStill() {
  const { paused, reduced } = useMotion();
  const r = useRef(false);
  r.current = paused || reduced;
  return r;
}

/* ── Scene 1: sculpted ASCII current running toward the harbor ── */
// Bands from faint to lit. Each band = one glyph + one fill style (batched draws).
const BANDS = [".", "·", ":", "-", "~", "=", "+", "*", "#"];
type HV = [number, number, number];

export function HarborField() {
  const { pointer } = useStage();
  const still = useStill();
  const view = useRef({ yaw: 0, pitch: 0 });
  const buf = useRef<{ n: number; z: Float32Array; b: Int8Array; ch: string[] } | null>(null);
  const ref = useCanvasLoop((ctx, w, h, t) => {
    const mobile = w < 768;
    const vw = view.current;
    if (!still.current) {
      vw.yaw += (clamp(pointer.current.tx, -1, 1) * 0.03 - vw.yaw) * 0.03 * MOTION_SPEED;
      vw.pitch += (clamp(pointer.current.ty, -1, 1) * 0.015 - vw.pitch) * 0.03 * MOTION_SPEED;
    }
    const leave = clamp(window.scrollY / (h * 0.9)); // swell relaxes into lanes as the hero scrolls away
    const cell = mobile ? 9 : w > 1700 ? 12 : 11;
    const cw = cell * 0.6;
    const cols = Math.ceil(w / cw), rows = Math.ceil(h / cell);
    const N = cols * rows;
    if (!buf.current || buf.current.n !== N) buf.current = { n: N, z: new Float32Array(N), b: new Int8Array(N), ch: new Array(N) };
    const { z: zb, b: bb, ch: cb } = buf.current;
    zb.fill(1e9); bb.fill(-1);

    // camera above a wide sea, looking slightly down; horizon sits near the top edge
    const yaw = -0.08 + vw.yaw, pitch = 0.3 + vw.pitch;
    const cY = Math.cos(yaw), sY = Math.sin(yaw), cP = Math.cos(pitch), sP = Math.sin(pitch);
    const CAM: HV = [0, 3.1, -2.5];
    const f = Math.max(w * 0.62, Math.min(h, window.innerHeight * 0.765) * 0.95);
    const ox = w * 0.5;
    const project = (p: HV) => {
      const x = p[0] - CAM[0], y = p[1] - CAM[1], z = p[2] - CAM[2];
      const x1 = x * cY - z * sY, z1 = x * sY + z * cY;
      const y1 = y * cP + z1 * sP, z2 = -y * sP + z1 * cP;
      if (z2 < 0.3) return null;
      return { x: ox + (x1 / z2) * f, y: h * 0.08 - (y1 / z2) * f, d: Math.hypot(x, y, z) };
    };

    // three sculpted currents sweep across the whole field (near-left → far-right), plus broad swell
    const amp = 1 - 0.7 * leave;
    const CUR = [
      { x0: -7.5, bend: 0.32, ph: 0, wd: 1.3, ht: 0.85 },
      { x0: -2.0, bend: 0.26, ph: 1.9, wd: 1.6, ht: 1.05 },
      { x0: 4.0, bend: 0.2, ph: 3.4, wd: 1.2, ht: 0.75 },
    ];
    const curX = (k: number, z: number) => { const c = CUR[k]!; return c.x0 + z * c.bend * 1.4 + Math.sin(z * 0.28 + c.ph) * 1.1; };
    const height = (x: number, z: number) => {
      let y = amp * (0.16 * Math.sin(x * 0.9 + z * 0.55 - t * 0.35) + 0.1 * Math.sin(x * 0.37 - z * 1.1 + t * 0.22));
      for (let k = 0; k < CUR.length; k++) {
        const c = CUR[k]!, dx = (x - curX(k, z)) / c.wd;
        const ridge = Math.exp(-dx * dx);
        y += ridge * (c.ht * (0.55 + 0.45 * Math.sin(z * 0.7 - t * 0.5 + c.ph)) * amp + 0.15);
      }
      return y;
    };
    const L: HV = [0.45, 0.72, 0.53];
    const ZF = 40;
    // broad attenuation behind the text block (soft, no hard rectangle) + a light touch under the header row
    const atten = (sx: number, sy: number) => {
      const u = sx / w, v = sy / h;
      const head = 1 - 0.45 * (1 - smooth(0.02, 0.07, v));
      const team = 1 - 0.72 * smooth(0.55, 0.8, v);
      if (mobile) return head * team * (1 - 0.6 * smooth(0.26, 0.42, v) * (1 - smooth(0.9, 1.02, v)));
      const dx = (u - 0.3) / 0.38, dy = (v - 0.68) / 0.46;
      return head * team * (1 - 0.72 * Math.exp(-(dx * dx + dy * dy) * 1.2));
    };
    // ray-cast every glyph cell onto the sea → the surface fills the whole hero edge to edge
    const Oy = h * 0.08;
    for (let j = 0; j < rows; j++) {
      const sy = j * cell + cell * 0.5;
      const y1 = -(sy - Oy) / f;
      for (let i = 0; i < cols; i++) {
        const sx = i * cw + cw * 0.5;
        const x1 = (sx - ox) / f;
        const dy = y1 * cP - sP, zc = y1 * sP + cP;
        const dx = x1 * cY + zc * sY, dz = -x1 * sY + zc * cY;
        if (dy > -0.02) continue;
        let tr = (CAM[1] - 0.3) / -dy;
        let x = 0, z = 0, y = 0;
        for (let it = 0; it < 3; it++) {
          x = CAM[0] + dx * tr; z = CAM[2] + dz * tr;
          y = height(x, z);
          tr = (CAM[1] - y) / -dy;
        }
        x = CAM[0] + dx * tr; z = CAM[2] + dz * tr;
        if (z > ZF || tr < 0.2) continue;
        const e = 0.05 + tr * 0.004;
        const hx = (height(x + e, z) - y) / e, hz = (height(x, z + e) - y) / e;
        let nx = -hx, ny = 1, nz = -hz; const nl = Math.hypot(nx, ny, nz); nx /= nl; ny /= nl; nz /= nl;
        const diff = Math.max(0, nx * L[0] + ny * L[1] + nz * L[2]);
        const vl = Math.hypot(dx, dy, dz);
        const qx = L[0] - dx / vl, qy = L[1] - dy / vl, qz = L[2] - dz / vl, ql = Math.hypot(qx, qy, qz);
        const spec = Math.pow(Math.max(0, (nx * qx + ny * qy + nz * qz) / ql), 22);
        const fog = 1 - smooth(8, ZF, z) * 0.8;
        const crest = clamp(y * 0.55);
        const near = 0.68 + 0.32 * smooth(1.5, 9, z); // keep the foreground calm so the eye rests mid-field
        const lum = (0.04 + diff * 0.3 + crest * 0.22 + spec * 1.0) * fog * near * atten(sx, sy);
        const k = j * cols + i;
        zb[k] = tr * vl;
        if (lum < 0.05) continue;
        const band = Math.min(BANDS.length - 1, Math.floor(lum * BANDS.length * 1.05));
        bb[k] = band; cb[k] = BANDS[band]!;
      }
    }
    // four luminous task lanes riding the currents (same identities + flow as the sequence below)
    const per = mobile ? 30 : 46;
    const laneHits: { x: number; y: number; a: number; g: string }[] = [];
    const laneCur = [0, 1, 1, 2], laneOff = [0, -0.35, 0.35, 0];
    for (let l = 0; l < LANES; l++) {
      for (let n = 0; n < per; n++) {
        const u = (n / per + t * FLOW) % 1;
        const z = 2.2 + u * 10;
        const x = curX(laneCur[l]!, z) + laneOff[l]! * CUR[laneCur[l]!]!.wd;
        const S = project([x, height(x, z) + 0.05, z]);
        if (!S) continue;
        const i = Math.floor(S.x / cw), j = Math.floor(S.y / cell);
        if (i < 0 || j < 0 || i >= cols || j >= rows) continue;
        const k = j * cols + i;
        if (S.d > zb[k]! * 1.05 + 0.3) continue;
        if (bb[k]! < 2) continue; // lanes only ride lit water, never float as stray glyphs
        const a = (0.55 + 0.35 * leave) * smooth(0, 0.08, u) * (1 - smooth(0.6, 0.9, u)) * atten(S.x, S.y);
        if (a < 0.03) continue;
        bb[k] = -1;
        laneHits.push({ x: i * cw, y: j * cell, a, g: glyphOf(l, n) });
      }
    }

    ctx.globalAlpha = 1;
    ctx.fillStyle = rgba(BG); ctx.fillRect(0, 0, w, h);
    ctx.font = `${cell}px "JetBrains Mono", monospace`;
    ctx.textBaseline = "top";
    for (let band = 0; band < BANDS.length; band++) {
      const q = band / (BANDS.length - 1);
      ctx.fillStyle = rgba(q > 0.85 ? FG : mix(MUTED, LINE, q));
      ctx.globalAlpha = 0.16 + q * 0.78;
      for (let k = 0; k < N; k++) if (bb[k] === band) ctx.fillText(cb[k]!, (k % cols) * cw, Math.floor(k / cols) * cell);
    }
    ctx.fillStyle = rgba(FG);
    for (const p of laneHits) { ctx.globalAlpha = p.a; ctx.fillText(p.g, p.x, p.y); }
    ctx.globalAlpha = 1;
  }, { dprCap: 1.5 });
  return <canvas ref={ref} aria-hidden className="absolute inset-0 h-full w-full" />;
}

export function HarborPage({ children }: { children: ReactNode }) {
 return <div className="theme-mono site-root bg-mono-bg text-mono-fg">
  <div className="site-intro">
   <HarborField />
   <div className="hero-type-scrim" aria-hidden="true"/>
  <section className="site-hero" id="top" aria-labelledby="hero-title">
   <SiteHeader/>
   <div className="site-shell hero-content">
    
    <p className="hero-brand display" aria-label="Task Harbor"><span>TASK</span><span>HARBOR</span></p>
    <h1 id="hero-title">A small engineering team.<br/><span>In your terminal.</span></h1>
    <p className="hero-description">AI agents plan, implement, verify, and review your coding backlog. You set the tasks and checks. You decide what gets merged.</p>
    <div className="hero-actions"><a href="#install" className="primary-link">Set up your team ↗</a><a href="#workflow" className="secondary-link">Explore a run ↓</a></div>
    <p className="hero-requirements">Uses your authenticated Claude Code or Codex account.</p>
   </div>
  </section>
  <EngineeringTeam/>
  </div>
  {children}
  <ReviewSection/>
  <GettingStarted/>
  <SiteClosing/>
 </div>;
}
