import { weekdayIndex } from "../../lib/format";
import type { Slot } from "../../lib/types";

/** Grid covers 06:00 to 22:00 in 30-minute cells (SPEC 8.2): 7 days x 32 rows. */
export const GRID_START = 6 * 60;
export const STEP = 30;
export const ROWS = 32;
export const GRID_END = GRID_START + ROWS * STEP;

export const idx = (day: number, row: number) => day * ROWS + row;
export const rowStart = (row: number) => GRID_START + row * STEP;

/** -1 = follow the weekly pattern, 0 = busy that date, 1 = free that date. */
export type Override = Int8Array;

export type CalState = {
  recurring: Uint8Array; // 1 = free every week
  overrides: Map<string, Override>; // keyed by YYYY-MM-DD
  outside: Slot[]; // slot parts outside 06:00-22:00, kept untouched on save
  recurringSource: Slot["source"]; // "timetable" once imported from a timetable
};

export function emptyState(): CalState {
  return { recurring: new Uint8Array(7 * ROWS), overrides: new Map(), outside: [], recurringSource: "manual" };
}

export function effective(s: CalState, date: string, day: number, row: number): 0 | 1 {
  const o = s.overrides.get(date);
  if (o && o[row] !== -1) return o[row] as 0 | 1;
  return s.recurring[idx(day, row)] as 0 | 1;
}

function newOverride() {
  return new Int8Array(ROWS).fill(-1);
}

/** Cells fully covered by [start, end) — never claims time that isn't free. */
function coveredRows(start: number, end: number): number[] {
  const rows: number[] = [];
  for (let r = 0; r < ROWS; r++) if (rowStart(r) >= start && rowStart(r) + STEP <= end) rows.push(r);
  return rows;
}

function outsideParts(s: Slot): Slot[] {
  const parts: Slot[] = [];
  if (s.start_min < GRID_START) parts.push({ ...s, end_min: Math.min(s.end_min, GRID_START) });
  if (s.end_min > GRID_END) parts.push({ ...s, start_min: Math.max(s.start_min, GRID_END) });
  return parts;
}

export function fromSlots(slots: Slot[]): CalState {
  const s = emptyState();
  for (const slot of slots) {
    s.outside.push(...outsideParts(slot));
    const rows = coveredRows(slot.start_min, slot.end_min);
    if (slot.recurring && !slot.date) {
      if (slot.kind === "free") rows.forEach((r) => (s.recurring[idx(slot.day_of_week, r)] = 1));
      if (slot.source === "timetable") s.recurringSource = "timetable";
      continue;
    }
    if (!slot.date) continue;
    const o = s.overrides.get(slot.date) ?? newOverride();
    rows.forEach((r) => (o[r] = slot.kind === "free" ? 1 : 0));
    s.overrides.set(slot.date, o);
  }
  return s;
}

function runs(values: ArrayLike<number>, want: number): [number, number][] {
  const out: [number, number][] = [];
  let start = -1;
  for (let r = 0; r <= ROWS; r++) {
    const on = r < ROWS && values[r] === want;
    if (on && start < 0) start = r;
    if (!on && start >= 0) {
      out.push([rowStart(start), rowStart(r)]);
      start = -1;
    }
  }
  return out;
}

export function toSlots(s: CalState): Slot[] {
  const slots: Slot[] = [...s.outside];
  for (let d = 0; d < 7; d++) {
    for (const [a, b] of runs(s.recurring.subarray(d * ROWS, (d + 1) * ROWS), 1)) {
      slots.push({ day_of_week: d, start_min: a, end_min: b, recurring: true, date: null, kind: "free", source: s.recurringSource });
    }
  }
  for (const [date, o] of s.overrides) {
    const day = weekdayIndex(date);
    for (const [want, kind] of [[1, "free"], [0, "busy_override"]] as const) {
      for (const [a, b] of runs(o, want)) {
        slots.push({ day_of_week: day, start_min: a, end_min: b, recurring: false, date, kind, source: "manual" });
      }
    }
  }
  return slots;
}

export type Cell = { day: number; row: number };
export type Mode = "weekly" | "week_only";

/** Returns a new state with `cells` set to `value`. In week-only mode it writes date overrides. */
export function applyCells(base: CalState, cells: Cell[], value: 0 | 1, mode: Mode, weekDates: string[]): CalState {
  if (mode === "weekly") {
    const recurring = base.recurring.slice();
    for (const c of cells) recurring[idx(c.day, c.row)] = value;
    return { ...base, recurring };
  }
  const overrides = new Map(base.overrides);
  const copied = new Set<string>();
  for (const c of cells) {
    const date = weekDates[c.day];
    if (!copied.has(date)) {
      overrides.set(date, overrides.get(date)?.slice() ?? newOverride());
      copied.add(date);
    }
    // An override equal to the weekly pattern is no override at all.
    overrides.get(date)![c.row] = base.recurring[idx(c.day, c.row)] === value ? -1 : value;
  }
  for (const [date, o] of overrides) if (o.every((v) => v === -1)) overrides.delete(date);
  return { ...base, overrides };
}

export function rect(a: Cell, b: Cell): Cell[] {
  const cells: Cell[] = [];
  for (let d = Math.min(a.day, b.day); d <= Math.max(a.day, b.day); d++)
    for (let r = Math.min(a.row, b.row); r <= Math.max(a.row, b.row); r++) cells.push({ day: d, row: r });
  return cells;
}

/** One weekday's cells that are fully covered by these [start, end) intervals. */
export function dayFromIntervals(intervals: { start_min: number; end_min: number }[]): Uint8Array {
  const out = new Uint8Array(ROWS);
  for (const iv of intervals) coveredRows(iv.start_min, iv.end_min).forEach((r) => (out[r] = 1));
  return out;
}

export function rowsBetween(day: number, fromMin: number, toMin: number): Cell[] {
  const cells: Cell[] = [];
  for (let r = 0; r < ROWS; r++) if (rowStart(r) >= fromMin && rowStart(r) + STEP <= toMin) cells.push({ day, row: r });
  return cells;
}
