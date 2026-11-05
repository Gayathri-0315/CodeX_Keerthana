import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronDown, ScanLine } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { addDays, formatMinutes, istToday, shortDate, weekdayIndex } from "../../lib/format";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { DAY_SHORT } from "../calendar/days";
import { Sheet } from "../ui/Sheet";

type Span = { start_min: number; end_min: number };
type Brief = Span & { event_id: string; title: string; category_slug: string | null; event_type: string };
type Fit = Brief & { match: number | null; fee_inr: number; organizer_name: string | null };
type Day = { date: string; free: Span[]; busy: Span[]; going: (Brief & { kind: "going" | "waitlist" })[]; recommended: Fit[]; fits: Fit[] };
export type Week = { start: string; day_start_min: number; day_end_min: number; has_free_time: boolean; fits_total: number; days: Day[] };

const EXPANDED_KEY = "showup-week-expanded";

/** Under ["feed"] so anything that refreshes the feed (free time, registrations, events) refreshes the week too. */
export function useWeek(start: string) {
  return useQuery({
    queryKey: ["feed", "week", start],
    queryFn: () => api<Week>(`/me/week?start=${start}`),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

function readExpanded() {
  try {
    return localStorage.getItem(EXPANDED_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * "Your week": free time (green), busy (grey), events you're going to (blue, amber on the waitlist) and up to two
 * events that fit each day as small outlined chips. One component for Home and the Calendar page.
 */
export function YourWeek({ weekOffset = 0, className = "" }: { weekOffset?: number; className?: string }) {
  const today = istToday();
  const start = addDays(today, -weekdayIndex(today) + weekOffset * 7);
  const { data: week, isPending, isError, refetch } = useWeek(start);
  const wide = useMediaQuery("(min-width: 768px)");
  const [expanded, setExpanded] = useState(readExpanded);
  const [selected, setSelected] = useState(() => (weekOffset === 0 ? weekdayIndex(today) : 0));
  const [sheetDay, setSheetDay] = useState<Day | null>(null);
  const picked = useRef(false);

  // Phones show one day: open on the first day from today that has free time or events, not an empty lane.
  useEffect(() => {
    if (!week || picked.current) return;
    picked.current = true;
    const from = weekOffset === 0 ? weekdayIndex(today) : 0;
    const busyish = (d: Day) => d.free.length > 0 || d.going.length > 0 || d.fits.length > 0;
    const next = week.days.findIndex((d, i) => i >= from && busyish(d));
    if (next >= 0) setSelected(next);
  }, [week, weekOffset, today]);

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    try {
      localStorage.setItem(EXPANDED_KEY, next ? "1" : "0");
    } catch {
      /* private mode: just not remembered */
    }
  };

  if (isError) {
    return (
      <div className={`card p-5 ${className}`}>
        <p className="headline">Couldn't load your week.</p>
        <button onClick={() => refetch()} className="callout mt-1 min-h-11 font-medium text-accent">Try again</button>
      </div>
    );
  }
  if (isPending) return <div className={`skeleton h-[268px] rounded-[22px] ${className}`} aria-busy="true" />;
  if (!week.has_free_time) return <EmptyWeek className={className} />;

  const laneHeight = expanded ? (wide ? 440 : 460) : wide ? 180 : 190;
  return (
    <section aria-labelledby="your-week" className={`card p-4 sm:p-5 ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 id="your-week" className="headline">Your week</h2>
          <p className="footnote text-text-2 tnum">
            {week.fits_total === 0 ? "Nothing fits your free time yet." : `${week.fits_total} ${week.fits_total === 1 ? "event fits" : "events fit"} your free time`}
          </p>
        </div>
        <button onClick={toggle} aria-expanded={expanded} className="pressable inline-flex min-h-11 items-center gap-1 rounded-full px-3 callout font-medium text-accent">
          {expanded ? "Collapse" : "Expand"}
          <ChevronDown className={`size-4 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </div>

      {wide ? (
        <div className="grid grid-cols-[2.5rem_repeat(7,minmax(0,1fr))] gap-1.5">
          <HourGutter week={week} height={laneHeight} offset={50} />
          {week.days.map((d, i) => (
            <div key={d.date} className="min-w-0">
              <button onClick={() => setSheetDay(d)} className={`pressable mb-1.5 flex w-full flex-col items-center rounded-[10px] py-1 hover:bg-text/5 ${d.date === today ? "text-accent" : ""}`}
                aria-label={`${DAY_SHORT[i]} ${shortDate(d.date)}: free time and events`}>
                <span className="footnote font-semibold">{DAY_SHORT[i]}</span>
                <span className="footnote text-text-2 tnum">{shortDate(d.date)}</span>
              </button>
              <Lane day={d} week={week} height={laneHeight} compact onOpenDay={() => setSheetDay(d)} />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="no-scrollbar -mx-4 mb-3 flex snap-x gap-1.5 overflow-x-auto px-4" role="tablist" aria-label="Day">
            {week.days.map((d, i) => {
              const active = i === selected;
              return (
                <button key={d.date} role="tab" aria-selected={active} onClick={() => setSelected(i)}
                  className={`pressable flex min-h-14 min-w-[46px] shrink-0 snap-start flex-col items-center justify-center rounded-[14px] px-2 ${active ? "bg-accent-fill text-white" : d.date === today ? "text-accent" : "text-text"}`}>
                  <span className="footnote font-semibold">{DAY_SHORT[i]}</span>
                  <span className={`footnote tnum ${active ? "text-white/85" : "text-text-2"}`}>{shortDate(d.date).split(" ")[0]}</span>
                  <span className={`mt-0.5 size-1.5 rounded-full ${d.fits.length ? (active ? "bg-white" : "bg-accent-fill") : "bg-transparent"}`} aria-hidden />
                </button>
              );
            })}
          </div>
          <div className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-1.5">
            <HourGutter week={week} height={laneHeight} offset={0} />
            <Lane key={selected} day={week.days[selected]} week={week} height={laneHeight} onOpenDay={() => setSheetDay(week.days[selected])} />
          </div>
        </>
      )}
      <DaySheet day={sheetDay} onClose={() => setSheetDay(null)} />
    </section>
  );
}

function top(m: number, week: Week, height: number) {
  return ((m - week.day_start_min) / (week.day_end_min - week.day_start_min)) * height;
}

function HourGutter({ week, height, offset }: { week: Week; height: number; offset: number }) {
  const marks = [6 * 60, 12 * 60, 18 * 60];
  return (
    <div className="relative" style={{ height, marginTop: offset }} aria-hidden>
      {marks.map((m) => (
        <span key={m} className="absolute right-0 -translate-y-1/2 text-[10px] text-text-2 tnum" style={{ top: Math.max(6, top(m, week, height)) }}>
          {formatMinutes(m)}
        </span>
      ))}
    </div>
  );
}

/** One day: grey busy base, green free windows, blue/amber going blocks, outlined chips for events that fit. */
function Lane({ day, week, height, compact = false, onOpenDay }: { day: Day; week: Week; height: number; compact?: boolean; onOpenDay: () => void }) {
  const navigate = useNavigate();
  // Chips never overlap: one line when the lane is short, two when it's tall; a later chip moves down if needed.
  const twoLines = height >= 300;
  const chipMin = twoLines ? 36 : 20;
  let floor = 0;
  const chips = [...day.recommended].sort((a, b) => a.start_min - b.start_min).map((r) => {
    const t = Math.max(top(r.start_min, week, height), floor);
    const h = Math.max(chipMin, top(r.end_min, week, height) - top(r.start_min, week, height));
    const placed = { r, top: Math.min(t, height - chipMin), height: Math.min(h, height - Math.min(t, height - chipMin)) };
    floor = placed.top + placed.height + 2;
    return placed;
  });
  const px = (s: Span) => ({ top: top(s.start_min, week, height), height: Math.max(4, top(s.end_min, week, height) - top(s.start_min, week, height)) });
  const freeLabel = day.free.map((f) => `${formatMinutes(f.start_min)} to ${formatMinutes(f.end_min)}`).join(", ");
  return (
    <div
      className="week-lane relative overflow-hidden rounded-[12px] bg-text/6"
      style={{ height }}
      role="group"
      aria-label={`Free ${freeLabel || "not at all"}. ${day.going.length} going, ${day.fits.length} that fit.`}
    >
      <button onClick={onOpenDay} className="absolute inset-0" aria-label="Open this day" />
      {day.free.map((f) => (
        <span key={`f${f.start_min}`} className="week-in pointer-events-none absolute inset-x-0 rounded-[8px] bg-free" style={px(f)} />
      ))}
      {day.going.map((g) => (
        <button
          key={g.event_id}
          onClick={() => navigate(`/event/${g.event_id}`)}
          className={`week-in absolute inset-x-[3px] overflow-hidden rounded-[8px] px-1.5 text-left text-[11px] font-semibold leading-tight ${g.kind === "going" ? "bg-accent-fill text-white" : "bg-warning/25 text-warning-text shadow-[inset_0_0_0_1px_var(--warning)]"}`}
          style={{ ...px(g), minHeight: 20 }}
          aria-label={`${g.kind === "going" ? "Going" : "Waitlist"}: ${g.title}, ${formatMinutes(g.start_min)}`}
        >
          <span className="block truncate pt-0.5">{g.title}</span>
        </button>
      ))}
      {chips.map(({ r, top: t, height: h }) => (
        <button
          key={r.event_id}
          onClick={() => navigate(`/event/${r.event_id}`)}
          className="week-in pressable absolute inset-x-[3px] overflow-hidden rounded-[8px] bg-surface px-1.5 text-left leading-tight text-text shadow-[inset_0_0_0_1.5px_var(--accent)]"
          style={{ top: t, height: h }}
          aria-label={`Fits: ${r.title}, ${formatMinutes(r.start_min)} to ${formatMinutes(r.end_min)}`}
        >
          {twoLines ? (
            <>
              <span className="block pt-0.5 text-[10px] font-semibold text-accent tnum">{formatMinutes(r.start_min)}</span>
              <span className="block truncate text-[11px] font-semibold">{r.title}</span>
            </>
          ) : (
            <span className={`block truncate text-[11px] font-semibold ${compact ? "" : "pt-px"}`}>
              <span className="text-accent tnum">{formatMinutes(r.start_min)}</span> {r.title}
            </span>
          )}
        </button>
      ))}
      {day.fits.length > day.recommended.length && (
        <button onClick={onOpenDay} className="pressable absolute bottom-1 left-1/2 -translate-x-1/2 rounded-full bg-surface px-2 py-0.5 text-[10px] font-semibold text-accent shadow-[0_1px_3px_rgba(0,0,0,0.12)]">
          +{day.fits.length - day.recommended.length}
        </button>
      )}
    </div>
  );
}

function DaySheet({ day, onClose }: { day: Day | null; onClose: () => void }) {
  const last = useRef<Day | null>(null);
  if (day) last.current = day;
  const d = day ?? last.current;
  const label = d ? new Date(`${d.date}T00:00:00Z`).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short", timeZone: "UTC" }) : "";
  return (
    <Sheet open={!!day} onClose={onClose} title={label}>
      {d && (
        <div className="flex max-h-[60dvh] flex-col gap-5 overflow-y-auto">
          <div>
            <p className="footnote mb-1.5 font-semibold uppercase tracking-wide text-text-2">Free</p>
            <p className="body tnum">{d.free.length ? d.free.map((f) => `${formatMinutes(f.start_min)} to ${formatMinutes(f.end_min)}`).join(", ") : "Not free this day."}</p>
          </div>
          {d.going.length > 0 && (
            <div>
              <p className="footnote mb-1.5 font-semibold uppercase tracking-wide text-text-2">Going</p>
              <ul className="flex flex-col gap-1">{d.going.map((g) => <EventRow key={g.event_id} e={g} onDone={onClose} note={g.kind === "waitlist" ? "Waitlist" : "Going"} />)}</ul>
            </div>
          )}
          <div>
            <p className="footnote mb-1.5 font-semibold uppercase tracking-wide text-text-2">Fits your free time</p>
            {d.fits.length ? (
              <ul className="flex flex-col gap-1">{d.fits.map((f) => <EventRow key={f.event_id} e={f} onDone={onClose} note={f.fee_inr ? `₹${f.fee_inr}` : "Free"} />)}</ul>
            ) : (
              <p className="callout text-text-2">No events fit this day yet.</p>
            )}
          </div>
        </div>
      )}
    </Sheet>
  );
}

function EventRow({ e, note, onDone }: { e: Brief; note: string; onDone: () => void }) {
  return (
    <li>
      <Link to={`/event/${e.event_id}`} onClick={onDone} className="pressable -mx-2 flex min-h-12 items-center justify-between gap-3 rounded-[12px] px-2 hover:bg-text/5">
        <span className="min-w-0">
          <span className="body block truncate">{e.title}</span>
          <span className="footnote block text-text-2 tnum">{formatMinutes(e.start_min)} to {formatMinutes(e.end_min)}</span>
        </span>
        <span className="footnote shrink-0 text-text-2">{note}</span>
      </Link>
    </li>
  );
}

function EmptyWeek({ className }: { className: string }) {
  return (
    <section className={`card p-5 ${className}`}>
      <h2 className="headline">Your week</h2>
      <p className="callout mt-1 text-text-2">Add your free time and we'll show the events that fit, right inside your week.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link to="/calendar?edit=1&import=1" className="pressable inline-flex min-h-11 items-center gap-1.5 rounded-[14px] bg-accent-fill px-4 font-semibold text-white">
          <ScanLine className="size-4" aria-hidden /> Import timetable
        </Link>
        <Link to="/calendar?edit=1" className="pressable inline-flex min-h-11 items-center gap-1.5 rounded-[14px] bg-accent-soft px-4 font-semibold text-accent">
          <CalendarDays className="size-4" aria-hidden /> Tap free hours
        </Link>
      </div>
    </section>
  );
}
