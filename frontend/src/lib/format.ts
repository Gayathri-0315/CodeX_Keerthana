export const TZ = "Asia/Kolkata";

const partsFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: TZ,
  weekday: "short",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "numeric",
  minute: "2-digit",
  hourCycle: "h23",
});

export function istParts(d: Date) {
  const p = Object.fromEntries(partsFmt.formatToParts(d).map((x) => [x.type, x.value]));
  return {
    weekday: p.weekday as string,
    year: Number(p.year),
    month: Number(p.month),
    day: Number(p.day),
    hour: Number(p.hour) % 24,
    minute: Number(p.minute),
  };
}

function clock(hour: number, minute: number, withSuffix = true) {
  const h = hour % 12 || 12;
  const body = minute ? `${h}:${String(minute).padStart(2, "0")}` : `${h}`;
  return withSuffix ? `${body} ${hour < 12 ? "AM" : "PM"}` : body;
}

/** "3 PM", "2:25 PM" */
export function formatTime(iso: string | Date) {
  const p = istParts(typeof iso === "string" ? new Date(iso) : iso);
  return clock(p.hour, p.minute);
}

/** "Sat, 3 to 5 PM" or "Sat, 11 AM to 1 PM" */
export function formatDayTime(startIso: string, endIso: string) {
  const s = istParts(new Date(startIso));
  const e = istParts(new Date(endIso));
  const sameHalf = s.hour < 12 === e.hour < 12;
  return `${s.weekday}, ${clock(s.hour, s.minute, !sameHalf)} to ${clock(e.hour, e.minute)}`;
}

/** "3 to 5 PM" */
export function formatTimeRange(startIso: string, endIso: string) {
  return formatDayTime(startIso, endIso).split(", ").slice(1).join(", ");
}

/** "Saturday, 31 Oct" */
export function formatLongDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short", timeZone: TZ });
}

/** Minutes since midnight -> "6 AM", "5:30 PM". */
export function formatMinutes(min: number) {
  return clock(Math.floor(min / 60) % 24, min % 60);
}

export function formatFee(inr: number) {
  return inr === 0 ? "Free" : `₹${inr.toLocaleString("en-IN")}`;
}

export function formatKm(km: number | null) {
  if (km == null) return "Online";
  return km < 1 ? "Under 1 km" : `${Math.round(km)} km away`;
}

/** Today's date in IST as YYYY-MM-DD. */
export function istToday(): string {
  const p = istParts(new Date());
  return isoDate(p.year, p.month, p.day);
}

export function isoDate(y: number, m: number, d: number) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** Add days to a YYYY-MM-DD string (calendar arithmetic, no timezone involved). */
export function addDays(iso: string, days: number) {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return isoDate(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
}

/** Monday = 0 */
export function weekdayIndex(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

export function shortDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
}

export function greeting() {
  const h = istParts(new Date()).hour;
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

/** "Apply by Fri, 7 Nov" (internships have a deadline, not a session time). */
export function formatApplyBy(iso: string) {
  return `Apply by ${new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: TZ })}`;
}

/** The time chip for any card: a session time, or the apply-by date for an internship. */
export function formatWhen(e: { event_type?: string; start_at: string; end_at: string }) {
  return e.event_type === "internship" ? formatApplyBy(e.start_at) : formatDayTime(e.start_at, e.end_at);
}
