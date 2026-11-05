import { AnimatePresence, m, useReducedMotion } from "motion/react";
import { Download, Pause, Play, RotateCcw, Share2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { periodOf, useRecap, type Recap } from "./recapData";
import { spring } from "../../lib/motion";

const SLIDE_MS = 5000;
const HOLD_MS = 200;
// Deep gradients so white text stays above AA contrast.
const BG: Record<string, string> = {
  intro: "linear-gradient(160deg, #0a2f6b 0%, #0057b8 100%)",
  events: "linear-gradient(160deg, #2e1065 0%, #6d28d9 100%)",
  hours: "linear-gradient(160deg, #064e3b 0%, #047857 100%)",
  topics: "linear-gradient(160deg, #831843 0%, #be185d 100%)",
  top: "linear-gradient(160deg, #7c2d12 0%, #b45309 100%)",
  streak: "linear-gradient(160deg, #1e1b4b 0%, #4338ca 100%)",
  style: "linear-gradient(160deg, #0c4a6e 0%, #0369a1 100%)",
  final: "linear-gradient(160deg, #0f172a 0%, #1e293b 100%)",
};

/** Which slides to show: skip empty ones; fewer than 3 events gives the short version. */
export function slidesFor(r: Recap): string[] {
  if (r.events_attended === 0) return ["intro"];
  if (r.short) return ["intro", "events", "final"];
  const all = ["intro", "events", "hours", "topics", "top", "streak", "style", "final"];
  return all.filter((s) =>
    s === "hours" ? r.hours > 0 : s === "topics" ? r.topics > 0 : s === "top" ? r.top_categories.length > 0 : s === "streak" ? r.longest_streak_weeks > 0 : true,
  );
}

/** Full-screen story viewer (a 9:16 panel on desktop). Lazy-loaded from the Record segment. */
export default function RecapViewer({ onClose }: { onClose: () => void }) {
  const [period, setPeriod] = useState(periodOf());
  const { data } = useRecap(period);
  const reduced = !!useReducedMotion();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [holding, setHolding] = useState(false);
  const holdTimer = useRef(0);
  const held = useRef(false);
  const slides = data ? slidesFor(data) : ["intro"];
  const last = slides.length - 1;
  const autoplay = !reduced && !paused && !holding && index < last;

  const go = useCallback((d: number) => setIndex((i) => Math.max(0, Math.min(last, i + d))), [last]);

  useEffect(() => setIndex((i) => Math.min(i, last)), [last]);
  useEffect(() => {
    if (!autoplay) return;
    const t = window.setTimeout(() => go(1), SLIDE_MS);
    return () => window.clearTimeout(t);
  }, [autoplay, index, go]);

  useEffect(() => {
    const prevFocus = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "Escape") onClose();
      else if (e.key === " ") {
        e.preventDefault();
        setPaused((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prevFocus?.focus?.();
    };
  }, [go, onClose]);

  // Tap left third = back, elsewhere = forward; press and hold = pause.
  const onDown = () => {
    held.current = false;
    holdTimer.current = window.setTimeout(() => {
      held.current = true;
      setHolding(true);
    }, HOLD_MS);
  };
  const onUp = (e: PointerEvent<HTMLDivElement>) => {
    window.clearTimeout(holdTimer.current);
    if (held.current) {
      setHolding(false);
      return;
    }
    const box = e.currentTarget.getBoundingClientRect();
    go(e.clientX - box.left < box.width / 3 ? -1 : 1);
  };
  const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

  return createPortal(
    <div className="fixed inset-0 z-[85] grid place-items-center bg-black/85" role="dialog" aria-modal="true" aria-label="Your semester recap">
      <div
        className="relative h-dvh w-full select-none overflow-hidden text-white md:h-[min(92dvh,860px)] md:w-auto md:aspect-[9/16] md:rounded-[22px]"
        onPointerDown={onDown}
        onPointerUp={onUp}
        onPointerCancel={() => {
          window.clearTimeout(holdTimer.current);
          setHolding(false);
        }}
      >
        <AnimatePresence initial={false} mode="popLayout">
          <m.div
            key={`${period}-${slides[index]}`}
            className="absolute inset-0"
            style={{ background: BG[slides[index]] }}
            initial={{ opacity: 0, scale: reduced ? 1 : 1.04 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: reduced ? 1 : 0.98 }}
            transition={reduced ? { duration: 0.2 } : { ...spring, opacity: { duration: 0.35 } }}
          >
            {data && <Slide kind={slides[index]} r={data} reduced={reduced} period={period} setPeriod={(p) => { setPeriod(p); setIndex(0); }}
              onReplay={() => setIndex(0)} stop={stop} />}
          </m.div>
        </AnimatePresence>

        {/* Progress, close and pause sit on top of every slide. */}
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 px-3 pt-[max(12px,env(safe-area-inset-top))]">
          <div className="flex gap-1" aria-hidden>
            {slides.map((s, i) => (
              <span key={s} className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/30">
                <span
                  key={`${index}-${paused || holding}`}
                  className={`block h-full origin-left bg-white ${i < index ? "" : i === index && autoplay ? "story-progress" : i === index && (reduced || index === last) ? "" : "scale-x-0"}`}
                  style={i === index && autoplay ? ({ "--story-ms": `${SLIDE_MS}ms` } as CSSProperties) : undefined}
                />
              </span>
            ))}
          </div>
          <div className="pointer-events-auto mt-2 flex justify-end gap-1">
            <button onPointerDown={stop} onPointerUp={stop} onClick={() => setPaused((p) => !p)} aria-label={paused ? "Play" : "Pause"}
              className="grid size-11 place-items-center rounded-full text-white/90 hover:bg-white/10">
              {paused ? <Play className="size-5" /> : <Pause className="size-5" />}
            </button>
            <button onPointerDown={stop} onPointerUp={stop} onClick={onClose} aria-label="Close recap" className="grid size-11 place-items-center rounded-full text-white/90 hover:bg-white/10">
              <X className="size-6" />
            </button>
          </div>
        </div>
        <p className="sr-only" aria-live="polite">Slide {index + 1} of {slides.length}</p>
      </div>
    </div>,
    document.body,
  );
}

// ---------------- slides ----------------

function In({ i, children, className = "" }: { i: number; children: ReactNode; className?: string }) {
  return <div className={`story-in ${className}`} style={{ "--i": i } as CSSProperties}>{children}</div>;
}

function Center({ children }: { children: ReactNode }) {
  return <div className="flex h-full flex-col justify-center px-8 pb-16 pt-24">{children}</div>;
}

function useCount(target: number, reduced: boolean, ms = 1200) {
  const [v, setV] = useState(reduced ? target : 0);
  useEffect(() => {
    if (reduced) return setV(target);
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      setV(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, reduced, ms]);
  return v;
}

function Big({ value, reduced, decimals = 0 }: { value: number; reduced: boolean; decimals?: number }) {
  const v = useCount(value, reduced);
  return <span className="block text-[112px] font-extrabold leading-none tracking-[-0.04em] tnum">{v.toFixed(decimals)}</span>;
}

function Slide({ kind, r, reduced, period, setPeriod, onReplay, stop }: {
  kind: string;
  r: Recap;
  reduced: boolean;
  period: string;
  setPeriod: (p: string) => void;
  onReplay: () => void;
  stop: (e: { stopPropagation: () => void }) => void;
}) {
  const year = new Date().getFullYear();
  switch (kind) {
    case "intro":
      return (
        <div className="relative h-full overflow-hidden">
          <div className="story-drift pointer-events-none absolute -inset-1/2" aria-hidden
            style={{ background: "radial-gradient(circle at 30% 30%, rgba(41,151,255,0.55), transparent 40%), radial-gradient(circle at 70% 65%, rgba(48,209,88,0.35), transparent 38%)" }} />
          <Center>
            <In i={0}><p className="text-[17px] font-semibold text-white/80">{r.first_name ? `${r.first_name}, this is` : "This is"}</p></In>
            <In i={1}><h2 className="mt-2 text-[44px] font-extrabold leading-[1.02] tracking-[-0.03em]">Your semester in events</h2></In>
            <In i={2}><p className="mt-4 text-[17px] text-white/85">{r.period_label}</p></In>
            <In i={3}>
              <div className="mt-8 inline-flex rounded-full bg-white/15 p-1" role="group" aria-label="Period" onPointerDown={stop} onPointerUp={stop}>
                {[`${year}-H1`, `${year}-H2`].map((p) => (
                  <button key={p} onClick={() => setPeriod(p)} aria-pressed={period === p}
                    className={`min-h-11 rounded-full px-4 text-[15px] font-semibold ${period === p ? "bg-white text-[#0a2f6b]" : "text-white"}`}>
                    {p.endsWith("H1") ? "Jan to Jun" : "Jul to Dec"}
                  </button>
                ))}
              </div>
            </In>
            {r.events_attended === 0 && <In i={4}><p className="mt-6 text-[17px] text-white/85">No checked-in events in this period yet.</p></In>}
          </Center>
        </div>
      );
    case "events":
      return (
        <Center>
          <In i={0}><Big value={r.events_attended} reduced={reduced} /></In>
          <In i={1}><p className="mt-3 text-[22px] font-semibold leading-snug">events you actually showed up to</p></In>
          <In i={2}>
            <div className="mt-8 flex flex-wrap gap-2" aria-hidden>
              {Array.from({ length: Math.min(r.events_attended, 30) }, (_, k) => (
                <span key={k} className="story-pop size-4 rounded-full bg-white" style={{ "--i": k } as CSSProperties} />
              ))}
            </div>
          </In>
        </Center>
      );
    case "hours": {
      const max = Math.max(10, Math.ceil(r.hours / 10) * 10);
      const lit = Math.round((r.hours / max) * 24);
      return (
        <Center>
          <In i={0}>
            <div className="relative mx-auto size-64" aria-hidden>
              {Array.from({ length: 24 }, (_, k) => (
                <span key={k} className="absolute left-1/2 top-0 h-full w-0" style={{ transform: `rotate(${k * 15}deg)` }}>
                  <span className={`story-tick absolute -left-[5px] top-0 h-7 w-[10px] rounded-full ${k < lit ? "bg-white" : "bg-white/20"}`}
                    style={{ "--i": k } as CSSProperties} />
                </span>
              ))}
              <div className="absolute inset-0 grid place-items-center"><Big value={r.hours} reduced={reduced} decimals={r.hours % 1 ? 1 : 0} /></div>
            </div>
          </In>
          <In i={1}><p className="mt-6 text-center text-[22px] font-semibold">hours learning, in the room</p></In>
        </Center>
      );
    }
    case "topics": {
      const most = Math.max(...r.categories.map((c) => c.count));
      return (
        <Center>
          <In i={0}><p className="text-[28px] font-extrabold leading-tight">You explored {r.topics} {r.topics === 1 ? "topic" : "topics"}</p></In>
          <div className="mt-8 flex flex-wrap items-end justify-center gap-3" aria-hidden>
            {r.categories.slice(0, 8).map((c, k) => {
              const size = 72 + (c.count / most) * 64;
              return (
                <span key={c.slug} className="story-rise grid place-items-center rounded-full bg-white/18 text-center" style={{ width: size, height: size, "--i": k + 1 } as CSSProperties}>
                  <span className="text-[30px] leading-none">{c.emoji}</span>
                </span>
              );
            })}
          </div>
          <In i={2}><p className="mt-6 text-center text-[15px] text-white/85">{r.categories.slice(0, 4).map((c) => c.name).join(" · ")}</p></In>
        </Center>
      );
    }
    case "top": {
      const top = r.top_categories[0];
      const max = top.count;
      return (
        <Center>
          <In i={0}><span className="cat-emoji grid size-24 place-items-center text-[72px] leading-none" data-motion="float" aria-hidden>{top.emoji}</span></In>
          <In i={1}><p className="mt-4 text-[17px] font-semibold text-white/85">Your favourite</p></In>
          <In i={2}><p className="text-[40px] font-extrabold leading-tight tracking-[-0.02em]">{top.name}</p></In>
          <div className="mt-8 flex flex-col gap-3">
            {r.top_categories.map((c, k) => (
              <div key={c.slug}>
                <div className="mb-1 flex justify-between text-[15px] font-semibold"><span>{c.emoji} {c.name}</span><span className="tnum">{c.count}</span></div>
                <div className="h-3 overflow-hidden rounded-full bg-white/20">
                  <div className="story-bar h-full origin-left rounded-full bg-white" style={{ transform: `scaleX(${c.count / max})`, "--i": k + 3 } as CSSProperties} />
                </div>
              </div>
            ))}
          </div>
        </Center>
      );
    }
    case "streak":
      return (
        <Center>
          <In i={0}><Big value={r.longest_streak_weeks} reduced={reduced} /></In>
          <In i={1}><p className="mt-3 text-[22px] font-semibold">{r.longest_streak_weeks === 1 ? "week" : "weeks"} in a row, your longest streak</p></In>
          <div className="mt-8 flex flex-wrap gap-2" aria-hidden>
            {Array.from({ length: Math.min(r.longest_streak_weeks, 20) }, (_, k) => (
              <span key={k} className="story-light h-8 w-6 rounded-[6px] bg-white" style={{ "--i": k } as CSSProperties} />
            ))}
          </div>
          {r.busiest_month && (
            <In i={3}><p className="mt-8 text-[17px] text-white/90">Busiest month: {r.busiest_month.month}, with {r.busiest_month.count} {r.busiest_month.count === 1 ? "event" : "events"}.</p></In>
          )}
        </Center>
      );
    case "style":
      return (
        <Center>
          <In i={0}><p className="text-[17px] font-semibold text-white/85">Your style</p></In>
          <In i={1}><p className="mt-2 text-[48px] font-extrabold leading-[1.02] tracking-[-0.03em]">{r.style.label}</p></In>
          <In i={2}><p className="mt-4 text-[22px] font-semibold leading-snug">{r.style.line}</p></In>
          <In i={3}><p className="mt-6 text-[17px] text-white/85">{r.style.reason}</p></In>
        </Center>
      );
    default:
      return <FinalSlide r={r} onReplay={onReplay} stop={stop} />;
  }
}

// ---------------- final card and sharing ----------------

function SummaryCard({ r, showCollege, exportSize = false }: { r: Recap; showCollege: boolean; exportSize?: boolean }) {
  // The same card on screen and in the 1080x1920 image (scaled up 3x for export).
  const k = exportSize ? 3 : 1;
  const px = (n: number) => `${n * k}px`;
  const stat = (v: ReactNode, l: string) => (
    <div style={{ padding: `${px(10)} 0` }}>
      <div style={{ fontSize: px(30), fontWeight: 800, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{v}</div>
      <div style={{ fontSize: px(13), opacity: 0.8, marginTop: px(4) }}>{l}</div>
    </div>
  );
  return (
    <div style={{ background: "linear-gradient(160deg,#0057b8,#6d28d9 60%,#be185d)", borderRadius: px(24), padding: px(24), color: "#fff",
      fontFamily: '-apple-system,BlinkMacSystemFont,"SF Pro Display","Inter Variable",Inter,"Segoe UI",system-ui,sans-serif' }}>
      <div style={{ fontSize: px(15), opacity: 0.85, fontWeight: 600 }}>{r.period_label}</div>
      <div style={{ fontSize: px(30), fontWeight: 800, lineHeight: 1.1, marginTop: px(6) }}>{r.first_name ? `${r.first_name}'s semester` : "My semester"}</div>
      {showCollege && r.college && <div style={{ fontSize: px(15), opacity: 0.85, marginTop: px(4) }}>{r.college}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: px(16), marginTop: px(18) }}>
        {stat(r.events_attended, "events attended")}
        {stat(r.hours % 1 ? r.hours.toFixed(1) : r.hours, "hours learning")}
        {stat(r.topics, "topics")}
        {stat(r.longest_streak_weeks, "week streak")}
      </div>
      <div style={{ marginTop: px(14), padding: `${px(12)} ${px(14)}`, background: "rgba(255,255,255,0.16)", borderRadius: px(14) }}>
        <div style={{ fontSize: px(13), opacity: 0.85 }}>My style</div>
        <div style={{ fontSize: px(22), fontWeight: 800 }}>{r.style.label}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: px(8), marginTop: px(18), fontSize: px(15), fontWeight: 700 }}>
        <svg viewBox="0 0 32 32" width={22 * k} height={22 * k} aria-hidden><rect width="32" height="32" rx="9" fill="#fff" /><path d="M10 16.5l4 4 8-9" stroke="#0057b8" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        ShowUp
      </div>
    </div>
  );
}

function FinalSlide({ r, onReplay, stop }: { r: Recap; onReplay: () => void; stop: (e: { stopPropagation: () => void }) => void }) {
  const [showCollege, setShowCollege] = useState(false);
  const [busy, setBusy] = useState<"share" | "save" | null>(null);
  const [exporting, setExporting] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  /** 1080x1920 PNG, made on this device. Nothing is uploaded and no link is created. */
  const makeImage = async (): Promise<Blob> => {
    setExporting(true);
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    await document.fonts.ready;
    const { toBlob } = await import("html-to-image");
    try {
      const blob = await toBlob(exportRef.current!, { width: 1080, height: 1920, pixelRatio: 1, cacheBust: true });
      if (!blob) throw new Error("Couldn't make the image.");
      return blob;
    } finally {
      setExporting(false);
    }
  };
  const save = (blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: `showup-recap-${r.period}.png` });
    a.click();
    URL.revokeObjectURL(url);
  };
  const share = async () => {
    setBusy("share");
    try {
      const blob = await makeImage();
      const file = new File([blob], `showup-recap-${r.period}.png`, { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) await navigator.share({ files: [file], title: "My semester in events" });
      else save(blob);
    } catch {
      /* the share sheet was closed */
    } finally {
      setBusy(null);
    }
  };
  const saveImage = async () => {
    setBusy("save");
    try {
      save(await makeImage());
    } finally {
      setBusy(null);
    }
  };

  const btn = "inline-flex min-h-11 items-center justify-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[14px] font-semibold";
  return (
    <div className="flex h-full flex-col justify-center px-6 pb-10 pt-24" onPointerDown={stop} onPointerUp={stop}>
      <In i={0}><SummaryCard r={r} showCollege={showCollege} /></In>
      {r.college && (
        <In i={1}>
          <label className="mt-4 flex min-h-11 items-center justify-between gap-3 text-[15px] text-white/90">
            Show my college
            <input type="checkbox" checked={showCollege} onChange={(e) => setShowCollege(e.target.checked)} className="size-5 accent-white" />
          </label>
        </In>
      )}
      <In i={2}>
        <div className="mt-4 grid grid-cols-[1fr_auto_1fr] gap-2">
          <button onClick={share} disabled={!!busy} className={`${btn} bg-white text-[#0f172a]`}><Share2 className="size-4" aria-hidden />{busy === "share" ? "…" : "Share"}</button>
          <button onClick={saveImage} disabled={!!busy} className={`${btn} bg-white/15 text-white`}><Download className="size-4" aria-hidden />{busy === "save" ? "…" : "Save image"}</button>
          <button onClick={onReplay} className={`${btn} bg-white/15 text-white`}><RotateCcw className="size-4" aria-hidden />Replay</button>
        </div>
      </In>
      {exporting && (
        <div className="pointer-events-none fixed left-[-20000px] top-0" aria-hidden>
          <div ref={exportRef} data-recap-export style={{ width: 1080, height: 1920, background: "#0f172a", display: "flex", alignItems: "center", padding: 96, boxSizing: "border-box" }}>
            <div style={{ width: "100%" }}><SummaryCard r={r} showCollege={showCollege} exportSize /></div>
          </div>
        </div>
      )}
    </div>
  );
}
