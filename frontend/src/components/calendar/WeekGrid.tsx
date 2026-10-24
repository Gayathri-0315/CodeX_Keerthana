import { memo, useCallback, useEffect, useRef, type KeyboardEvent, type PointerEvent } from "react";
import { formatMinutes, shortDate } from "../../lib/format";
import { haptic } from "../../lib/motion";
import { DAY_SHORT, DAY_LONG } from "./days";
import { ROWS, STEP, effective, rect, rowStart, type CalState, type Cell } from "./model";

type Props = {
  state: CalState;
  weekDates: string[];
  today: string;
  /** Which days to render, and how: one 7-column grid, or one column per day (phone pager). */
  days: number[];
  layout: "week" | "day";
  focus: Cell;
  onFocus: (c: Cell) => void;
  onPaintStart: () => void;
  onPaint: (cells: Cell[], value: 0 | 1) => void;
  onPaintEnd: () => void;
  onToggleDay: (day: number) => void;
};

const HOLD_MS = 180;
const MOVE_TOLERANCE = 8;

function cellAt(x: number, y: number): Cell | null {
  // elementsFromPoint looks through floating UI (the fit pill) that sits over the grid.
  const hit = document.elementsFromPoint(x, y).find((e) => (e as HTMLElement).closest?.("[data-cell]"));
  const el = (hit as HTMLElement | undefined)?.closest<HTMLElement>("[data-cell]");
  if (!el) return null;
  const [day, row] = el.dataset.cell!.split(":").map(Number);
  return { day, row };
}

/**
 * Paint grid. Mouse/pen paint on press; touch paints after a short hold so a normal swipe still scrolls.
 * Drags paint the rectangle from the first cell to the current one, applied once per animation frame.
 */
export function WeekGrid(p: Props) {
  const root = useRef<HTMLDivElement>(null);
  const drag = useRef<{ anchor: Cell; last: Cell; value: 0 | 1 } | null>(null);
  const frame = useRef(0);
  const latest = useRef(p);
  latest.current = p;

  const valueFor = (c: Cell): 0 | 1 => {
    const { state, weekDates } = latest.current;
    return effective(state, weekDates[c.day], c.day, c.row) ? 0 : 1;
  };

  const flush = useCallback(() => {
    frame.current = 0;
    const d = drag.current;
    if (d) latest.current.onPaint(rect(d.anchor, d.last), d.value);
  }, []);

  const start = (c: Cell) => {
    drag.current = { anchor: c, last: c, value: valueFor(c) };
    latest.current.onPaintStart();
    latest.current.onFocus(c);
    flush();
  };
  const move = (c: Cell | null) => {
    const d = drag.current;
    if (!d || !c || (c.day === d.last.day && c.row === d.last.row)) return;
    d.last = c;
    if (!frame.current) frame.current = requestAnimationFrame(flush);
  };
  const end = () => {
    if (!drag.current) return;
    cancelAnimationFrame(frame.current);
    flush();
    drag.current = null;
    latest.current.onPaintEnd();
  };

  // ---- mouse and pen ----
  const onPointerDown = (e: PointerEvent) => {
    if (e.pointerType === "touch" || e.button !== 0) return;
    const c = cellAt(e.clientX, e.clientY);
    if (!c) return;
    e.preventDefault();
    root.current?.setPointerCapture(e.pointerId);
    start(c);
  };
  const onPointerMove = (e: PointerEvent) => {
    if (e.pointerType !== "touch" && drag.current) move(cellAt(e.clientX, e.clientY));
  };

  // ---- touch: tap toggles, hold-then-drag paints, quick swipe scrolls ----
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    let timer = 0;
    let origin: { x: number; y: number; cell: Cell } | null = null;
    const clear = () => {
      window.clearTimeout(timer);
      timer = 0;
    };
    const onStart = (e: TouchEvent) => {
      if (e.touches.length !== 1) return clear();
      const t = e.touches[0];
      const cell = cellAt(t.clientX, t.clientY);
      if (!cell) return;
      origin = { x: t.clientX, y: t.clientY, cell };
      timer = window.setTimeout(() => {
        timer = 0;
        haptic(8);
        start(cell);
      }, HOLD_MS);
    };
    const onMove = (e: TouchEvent) => {
      const t = e.touches[0];
      if (drag.current) {
        e.preventDefault(); // painting: stop the page from scrolling
        move(cellAt(t.clientX, t.clientY));
      } else if (origin && Math.hypot(t.clientX - origin.x, t.clientY - origin.y) > MOVE_TOLERANCE) {
        clear(); // it's a scroll
        origin = null;
      }
    };
    const onEnd = () => {
      if (timer && origin) {
        clear(); // quick tap: toggle one cell
        start(origin.cell);
        end();
      } else {
        end();
      }
      origin = null;
    };
    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: false });
    el.addEventListener("touchend", onEnd);
    el.addEventListener("touchcancel", onEnd);
    return () => {
      clear();
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
      el.removeEventListener("touchcancel", onEnd);
    };
  }, []);

  // ---- keyboard: arrows move, Space toggles, Shift+arrows extend ----
  const onKeyDown = (e: KeyboardEvent) => {
    const { focus, days } = latest.current;
    const deltas: Record<string, [number, number]> = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      start(focus);
      end();
      return;
    }
    const delta = deltas[e.key];
    if (!delta) return;
    e.preventDefault();
    const dayPos = days.indexOf(focus.day);
    const next: Cell = {
      day: days[Math.max(0, Math.min(days.length - 1, dayPos + delta[0]))] ?? focus.day,
      row: Math.max(0, Math.min(ROWS - 1, focus.row + delta[1])),
    };
    if (e.shiftKey) {
      const v = effective(latest.current.state, latest.current.weekDates[focus.day], focus.day, focus.row);
      latest.current.onPaintStart();
      latest.current.onPaint([next], v);
      latest.current.onPaintEnd();
    }
    latest.current.onFocus(next);
    root.current?.querySelector<HTMLElement>(`[data-cell="${next.day}:${next.row}"]`)?.focus();
  };

  const { state, weekDates, today, days, layout, focus } = p;
  const cols = layout === "week" ? `3.25rem repeat(${days.length}, minmax(0, 1fr))` : "3.25rem minmax(0, 1fr)";

  return (
    <div
      ref={root}
      role="grid"
      aria-label="Free time. Free hours are green."
      aria-rowcount={ROWS + 1}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={(e) => e.pointerType !== "touch" && end()}
      onPointerCancel={(e) => e.pointerType !== "touch" && end()}
      onLostPointerCapture={(e) => e.pointerType !== "touch" && end()}
      onKeyDown={onKeyDown}
      className="select-none"
      style={{ display: "grid", gridTemplateColumns: cols, touchAction: "pan-x pan-y" }}
    >
      <div role="row" className="contents">
        <div className="sticky top-0 z-10 bg-surface md:top-14" role="columnheader" aria-label="Time" />
        {days.map((d) => (
          <div key={d} role="columnheader" className="sticky top-0 z-10 bg-surface pb-2 md:top-14">
            <button
              onClick={() => p.onToggleDay(d)}
              className={`pressable flex min-h-11 w-full flex-col items-center justify-center rounded-[12px] hover:bg-text/5 ${weekDates[d] === today ? "text-accent" : ""}`}
              aria-label={`Toggle all of ${DAY_LONG[d]}`}
            >
              <span className="footnote font-semibold">{DAY_SHORT[d]}</span>
              <span className="footnote text-text-2 tnum">{shortDate(weekDates[d])}</span>
            </button>
          </div>
        ))}
      </div>
      {Array.from({ length: ROWS }, (_, row) => (
        <div role="row" className="contents" key={row}>
          <div role="rowheader" className="relative pr-2 text-right">
            {row % 2 === 0 && <span className={`absolute right-2 text-[11px] text-text-2 tnum ${row === 0 ? "top-0" : "-top-2"}`}>{formatMinutes(rowStart(row))}</span>}
          </div>
          {days.map((d) => {
            const date = weekDates[d];
            const free = effective(state, date, d, row) === 1;
            const o = state.overrides.get(date)?.[row] ?? -1;
            return (
              <GridCell
                key={d}
                day={d}
                row={row}
                free={free}
                override={o !== -1}
                joinTop={row > 0 && effective(state, date, d, row - 1) === 1}
                joinBottom={row < ROWS - 1 && effective(state, date, d, row + 1) === 1}
                focused={focus.day === d && focus.row === row}
                tall={layout === "day"}
                onFocus={p.onFocus}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

type CellProps = {
  day: number;
  row: number;
  free: boolean;
  override: boolean;
  joinTop: boolean;
  joinBottom: boolean;
  focused: boolean;
  tall: boolean;
  onFocus: (c: Cell) => void;
};

/** Memoized: a drag re-renders only cells whose look actually changed. */
const GridCell = memo(function GridCell({ day, row, free, override, joinTop, joinBottom, focused, tall, onFocus }: CellProps) {
  const label = `${DAY_LONG[day]} ${formatMinutes(rowStart(row))} to ${formatMinutes(rowStart(row) + STEP)}, ${free ? "free" : "busy"}${override ? ", this week only" : ""}`;
  return (
    <div
      role="gridcell"
      aria-selected={free}
      aria-label={label}
      data-cell={`${day}:${row}`}
      tabIndex={focused ? 0 : -1}
      onFocus={() => onFocus({ day, row })}
      className={`relative px-[2px] outline-none ${tall ? "h-7" : "h-[22px]"} ${row % 2 === 0 ? "border-t border-line" : ""} focus-visible:z-[1] focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset`}
    >
      <div
        className={`absolute inset-x-[2px] transition-[background-color] duration-150 ${free ? "bg-free" : ""} ${
          free && !joinTop ? "top-[2px] rounded-t-[8px]" : "top-0"
        } ${free && !joinBottom ? "bottom-[2px] rounded-b-[8px]" : "bottom-0"} ${
          override ? (free ? "shadow-[inset_3px_0_0_var(--accent)]" : "bg-[repeating-linear-gradient(135deg,var(--override)_0_4px,transparent_4px_8px)]") : ""
        }`}
      />
    </div>
  );
});
