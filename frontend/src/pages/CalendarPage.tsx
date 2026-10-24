import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { ChevronLeft, ChevronRight, CloudOff, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { DAY_SHORT } from "../components/calendar/days";
import {
  applyCells,
  effective,
  fromSlots,
  ROWS,
  rowsBetween,
  toSlots,
  type CalState,
  type Cell,
  type Mode,
} from "../components/calendar/model";
import { WeekGrid } from "../components/calendar/WeekGrid";
import { Button } from "../components/ui/Button";
import { CountUp } from "../components/ui/CountUp";
import { Segmented } from "../components/ui/Segmented";
import { useToast } from "../components/ui/Toaster";
import { api } from "../lib/api";
import { addDays, istToday, shortDate, weekdayIndex } from "../lib/format";
import { gentle, haptic, spring } from "../lib/motion";
import { keys, useAvailability, useFeedCount, useUpdateMe } from "../lib/queries";
import type { Slot } from "../lib/types";
import { useMediaQuery } from "../lib/useMediaQuery";

const SAVE_DEBOUNCE_MS = 400;

export default function CalendarPage() {
  const { data: slots, isPending, isError, refetch } = useAvailability();
  const [params] = useSearchParams();
  const onboarding = params.get("onboarding") === "1";

  return (
    <>
      <PageHeader
        title="Your free time"
        subtitle="Paint the hours you're free. We only show events that fit."
        action={onboarding ? <OnboardingDone /> : undefined}
      />
      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load your free time.</p>
          <Button variant="secondary" className="mt-4" onClick={() => refetch()}>Try again</Button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-[720px] rounded-[22px]" aria-busy="true" />
      ) : (
        <Editor initial={slots} />
      )}
    </>
  );
}

type SaveState = "idle" | "saving" | "saved" | "error";

function Editor({ initial }: { initial: Slot[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const wide = useMediaQuery("(min-width: 768px)");
  const today = istToday();
  const [weekOffset, setWeekOffset] = useState(0);
  const [mode, setMode] = useState<Mode>("weekly");
  const [state, setState] = useState<CalState>(() => fromSlots(initial));
  const [focus, setFocus] = useState<Cell>({ day: weekdayIndex(today), row: 22 });
  const [saveState, setSaveState] = useState<SaveState>("idle");

  const monday = addDays(today, -weekdayIndex(today) + weekOffset * 7);
  const weekDates = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(monday, i)), [monday]);

  // ---- batched, debounced save (one PUT for the whole slot set) ----
  const stateRef = useRef(state);
  stateRef.current = state;
  const timer = useRef(0);
  const save = useMutation({
    mutationFn: (s: CalState) => api<{ slots: Slot[] }>("/availability", { method: "PUT", body: { slots: toSlots(s) } }),
    onSuccess: (res) => {
      qc.setQueryData(keys.availability, res.slots);
      qc.invalidateQueries({ queryKey: keys.feedAll });
      setSaveState("saved");
    },
    onError: async (e) => {
      setSaveState("error");
      toast({ tone: "error", title: "Couldn't save your free time", body: (e as Error).message });
      // Roll back to what the server has.
      const fresh = await qc.fetchQuery({ queryKey: keys.availability, queryFn: () => api<{ slots: Slot[] }>("/availability").then((r) => r.slots) }).catch(() => null);
      if (fresh) setState(fromSlots(fresh));
    },
  });
  const scheduleSave = useCallback(() => {
    setSaveState("saving");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      timer.current = 0;
      save.mutate(stateRef.current);
    }, SAVE_DEBOUNCE_MS);
  }, [save]);
  // Flush a pending save if the user leaves the page mid-debounce.
  useEffect(() => () => {
    if (timer.current) {
      window.clearTimeout(timer.current);
      api("/availability", { method: "PUT", body: { slots: toSlots(stateRef.current) } })
        .then(() => {
          qc.invalidateQueries({ queryKey: keys.availability });
          qc.invalidateQueries({ queryKey: keys.feedAll });
        })
        .catch(() => {});
    }
  }, [qc]);

  // ---- painting ----
  const snapshot = useRef<CalState | null>(null);
  const onPaintStart = useCallback(() => {
    snapshot.current = stateRef.current;
  }, []);
  const onPaint = useCallback(
    (cells: Cell[], value: 0 | 1) => setState(applyCells(snapshot.current ?? stateRef.current, cells, value, mode, weekDates)),
    [mode, weekDates],
  );
  const onPaintEnd = useCallback(() => {
    snapshot.current = null;
    scheduleSave();
  }, [scheduleSave]);

  const setCells = (cells: Cell[], value: 0 | 1) => {
    setState((s) => applyCells(s, cells, value, mode, weekDates));
    haptic();
    scheduleSave();
  };
  const toggleDay = (day: number) => {
    const all = Array.from({ length: ROWS }, (_, row) => ({ day, row }));
    const allFree = all.every((c) => effective(stateRef.current, weekDates[day], day, c.row) === 1);
    setCells(all, allFree ? 0 : 1);
  };
  const presets = [
    { label: "Weekdays after 5 PM", run: () => setCells([0, 1, 2, 3, 4].flatMap((d) => rowsBetween(d, 17 * 60, 22 * 60)), 1) },
    { label: "Weekends", run: () => setCells([5, 6].flatMap((d) => rowsBetween(d, 8 * 60, 22 * 60)), 1) },
    { label: "Clear", run: () => setCells([0, 1, 2, 3, 4, 5, 6].flatMap((d) => rowsBetween(d, 0, 24 * 60)), 0) },
  ];

  const gridProps = { state, weekDates, today, focus, onFocus: setFocus, onPaintStart, onPaint, onPaintEnd, onToggleDay: toggleDay };
  const weekLabel = weekOffset === 0 ? "This week" : weekOffset === 1 ? "Next week" : `In ${weekOffset} weeks`;

  return (
    <div className="pb-24">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Edit mode"
          value={mode}
          onChange={setMode}
          options={[
            { value: "weekly", label: "Every week" },
            { value: "week_only", label: weekOffset === 0 ? "This week only" : "That week only" },
          ]}
        />
        <div className="flex items-center gap-1" aria-label="Week">
          <button aria-label="Previous week" disabled={weekOffset === 0} onClick={() => setWeekOffset((w) => w - 1)} className="pressable grid size-11 place-items-center rounded-full text-accent disabled:opacity-30">
            <ChevronLeft className="size-5" />
          </button>
          <span className="callout min-w-[150px] text-center font-medium tnum" aria-live="polite">
            {weekLabel} · {shortDate(weekDates[0])} to {shortDate(weekDates[6])}
          </span>
          <button aria-label="Next week" disabled={weekOffset === 3} onClick={() => setWeekOffset((w) => w + 1)} className="pressable grid size-11 place-items-center rounded-full text-accent disabled:opacity-30">
            <ChevronRight className="size-5" />
          </button>
        </div>
      </div>

      <div className="no-scrollbar -mx-4 mb-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        {presets.map((p) => (
          <button key={p.label} onClick={p.run} className="pressable min-h-11 shrink-0 rounded-full bg-surface px-4 callout font-medium shadow-[inset_0_0_0_1px_var(--line)]">
            {p.label}
          </button>
        ))}
      </div>

      {mode === "week_only" && (
        <p className="footnote mb-3 text-text-2">
          Changes apply to {weekLabel.toLowerCase()} only. <span className="inline-block h-3 w-3 translate-y-0.5 rounded-sm bg-[repeating-linear-gradient(135deg,var(--override)_0_3px,transparent_3px_6px)]" aria-hidden /> marks a one-off change.
        </p>
      )}

      {wide ? (
        <div className="card p-3 pr-4">
          <WeekGrid {...gridProps} days={[0, 1, 2, 3, 4, 5, 6]} layout="week" />
        </div>
      ) : (
        <DayPager {...gridProps} />
      )}

      <FitPill saveState={saveState} />
    </div>
  );
}

/** Phones: a compact week overview plus a horizontally snapping one-day-per-page pager. */
function DayPager(props: Omit<Parameters<typeof WeekGrid>[0], "days" | "layout">) {
  const pager = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(props.focus.day);

  useEffect(() => {
    const el = pager.current;
    if (!el) return;
    el.scrollTo({ left: el.clientWidth * props.focus.day, behavior: "instant" as ScrollBehavior });
    // Only on mount: later focus changes come from the user and are already in view.
  }, []);

  const onScroll = () => {
    const el = pager.current;
    if (el) setVisible(Math.round(el.scrollLeft / el.clientWidth));
  };
  const goTo = (d: number) => pager.current?.scrollTo({ left: pager.current.clientWidth * d, behavior: "smooth" });

  return (
    <>
      <div className="card mb-3 grid grid-cols-7 gap-1 p-2" role="tablist" aria-label="Week overview">
        {DAY_SHORT.map((label, d) => (
          <button key={d} role="tab" aria-selected={visible === d} onClick={() => goTo(d)} className={`pressable flex min-h-11 flex-col items-center gap-1 rounded-[10px] py-1 ${visible === d ? "bg-accent-soft" : ""}`}>
            <span className={`text-[11px] font-semibold ${props.weekDates[d] === props.today ? "text-accent" : "text-text-2"}`}>{label}</span>
            <span className="relative h-8 w-2 overflow-hidden rounded-full bg-text/8" aria-hidden>
              {Array.from({ length: ROWS }, (_, r) =>
                effective(props.state, props.weekDates[d], d, r) ? (
                  <span key={r} className="absolute inset-x-0 bg-success" style={{ top: `${(r / ROWS) * 100}%`, height: `${100 / ROWS + 0.5}%` }} />
                ) : null,
              )}
            </span>
          </button>
        ))}
      </div>
      <p className="footnote mb-2 text-text-2">Tap an hour, or hold and drag to paint.</p>
      <div ref={pager} onScroll={onScroll} className="no-scrollbar -mx-4 flex snap-x snap-mandatory overflow-x-auto">
        {[0, 1, 2, 3, 4, 5, 6].map((d) => (
          <div key={d} className="w-full shrink-0 snap-center px-4">
            <div className="card p-3 pr-4">
              <WeekGrid {...props} days={[d]} layout="day" />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function FitPill({ saveState }: { saveState: SaveState }) {
  const { data } = useFeedCount();
  const navigate = useNavigate();
  const fits = data?.fits ?? 0;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom,0px)+72px)] z-30 flex justify-center px-4 md:bottom-8">
      <m.button
        initial={{ y: 30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={gentle}
        onClick={() => navigate("/")}
        className="glass pressable pointer-events-auto flex min-h-12 items-center gap-2 rounded-full py-2 pl-5 pr-3 shadow-[0_8px_30px_rgba(0,0,0,0.16)] ring-1 ring-line"
        aria-live="polite"
      >
        <span className="headline">
          <CountUp value={fits} /> {fits === 1 ? "event fits" : "events fit"} your free time
        </span>
        <span className="grid size-6 place-items-center text-text-2" aria-label={saveState === "saving" ? "Saving" : saveState === "error" ? "Not saved" : "Saved"}>
          {saveState === "saving" ? <Loader2 className="size-4 animate-spin" /> : saveState === "error" ? <CloudOff className="size-4 text-danger" /> : <ChevronRight className="size-5" />}
        </span>
      </m.button>
    </div>
  );
}

function OnboardingDone() {
  const update = useUpdateMe();
  const navigate = useNavigate();
  const [done, setDone] = useState(false);

  const finish = () =>
    update.mutate(
      { onboarded: true },
      {
        onSuccess: () => {
          setDone(true);
          haptic();
          window.setTimeout(() => navigate("/", { replace: true }), 1100);
        },
      },
    );

  return (
    <>
      <Button onClick={finish} loading={update.isPending}>Done</Button>
      <AnimatePresence>
        {done && (
          <m.div className="fixed inset-0 z-[55] grid place-items-center bg-bg/80 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <m.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={spring} className="flex flex-col items-center gap-4">
              <span className="grid size-24 place-items-center rounded-full bg-success text-white">
                <svg viewBox="0 0 24 24" className="size-12" aria-hidden>
                  <m.path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, delay: 0.15 }} />
                </svg>
              </span>
              <p className="title-2">You're all set</p>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </>
  );
}
