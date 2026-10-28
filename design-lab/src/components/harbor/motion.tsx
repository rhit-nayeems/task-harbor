import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

type Motion = { paused: boolean; reduced: boolean; setPaused: (p: boolean) => void };
const Ctx = createContext<Motion>({ paused: false, reduced: false, setPaused: () => {} });

export function MotionProvider({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("motion-paused", paused || reduced);
  }, [paused, reduced]);
  return <Ctx.Provider value={{ paused, reduced, setPaused }}>{children}</Ctx.Provider>;
}

export const useMotion = () => useContext(Ctx);

/** Pointer (normalized -1..1) and scroll progress refs, updated without re-render. */
export function useStage() {
  const pointer = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const scroll = useRef(0);
  useEffect(() => {
    const mv = (e: PointerEvent) => {
      pointer.current.tx = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.ty = (e.clientY / window.innerHeight) * 2 - 1;
    };
    const sc = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      scroll.current = max > 0 ? window.scrollY / max : 0;
    };
    sc();
    window.addEventListener("pointermove", mv, { passive: true });
    window.addEventListener("scroll", sc, { passive: true });
    return () => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("scroll", sc);
    };
  }, []);
  return { pointer, scroll };
}

/**
 * Runs a canvas render loop with DPR sizing. draw(t) receives seconds.
 * When paused/reduced, a single static frame is drawn.
 */
export function useCanvasLoop(
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => void,
  opts: { dprCap?: number } = {},
) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { paused, reduced } = useMotion();
  const drawRef = useRef(draw);
  drawRef.current = draw;
  const tRef = useRef(0);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    let w = 0, h = 0, raf = 0, last = performance.now();
    let visible = true;
    const still = paused || reduced;
    const size = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, opts.dprCap ?? 2, c.clientWidth < 640 ? 1.5 : 3);
      w = c.clientWidth; h = c.clientHeight;
      c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawRef.current(ctx, w, h, tRef.current);
    };
    size();
    const ro = new ResizeObserver(size);
    ro.observe(c);
    const running = () => !still && visible && !document.hidden;
    const loop = (now: number) => {
      if (!running()) { raf = 0; return; }
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      tRef.current += dt;
      drawRef.current(ctx, w, h, tRef.current);
      raf = requestAnimationFrame(loop);
    };
    const kick = () => {
      if (running() && !raf) { last = performance.now(); raf = requestAnimationFrame(loop); }
    };
    // Stop when offscreen (with margin) or tab hidden.
    const io = new IntersectionObserver(([e]) => { visible = !!e?.isIntersecting; kick(); }, { rootMargin: "150px" });
    io.observe(c);
    document.addEventListener("visibilitychange", kick);
    // When still, redraw a frozen frame on scroll so scroll-driven scenes stay readable.
    let sraf = 0;
    const onScroll = () => {
      if (!still || !visible || sraf) return;
      sraf = requestAnimationFrame(() => { sraf = 0; drawRef.current(ctx, w, h, reduced ? 4 : tRef.current); });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    if (still) drawRef.current(ctx, w, h, reduced ? 4 : tRef.current);
    else kick();
    return () => {
      cancelAnimationFrame(raf); cancelAnimationFrame(sraf); ro.disconnect(); io.disconnect();
      document.removeEventListener("visibilitychange", kick);
      window.removeEventListener("scroll", onScroll);
    };
  }, [paused, reduced, opts.dprCap]);
  return ref;
}

/** Adds data-in="1" when element enters viewport. */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [inView, setIn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => e?.isIntersecting && setIn(true), { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, inView] as const;
}

export type Palette = { ivory: string; signal: string; bg: string; forest: string; lit: string; ink: string; paper: string };
export function readPalette(): Palette {
  const s = getComputedStyle(document.documentElement);
  const v = (n: string) => s.getPropertyValue(n).trim();
  return { ivory: v("--ivory"), signal: v("--signal"), bg: v("--forest-deep"), forest: v("--forest"), lit: v("--forest-lit"), ink: v("--forest-deep"), paper: v("--ivory") };
}

