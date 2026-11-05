import { m } from "motion/react";
import { CircleCheck, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import { formatFee, formatTimeRange, istParts, isoDate, istToday, addDays } from "../../lib/format";
import { easeOut } from "../../lib/motion";
import { usePrefetchEvent } from "../../lib/queries";
import type { FeedItem } from "../../lib/types";
import { Tag } from "../ui/Chip";
import { OrganizerLabel } from "../landing/PublicEventCard";
import { Thumb } from "./EventCard";
import { ClubName } from "./ClubName";

/** IST calendar date of an event, "YYYY-MM-DD". */
function dayKey(iso: string) {
  const p = istParts(new Date(iso));
  return isoDate(p.year, p.month, p.day);
}

function dayHeading(key: string) {
  const today = istToday();
  const label = new Date(`${key}T00:00:00Z`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
  if (key === today) return { main: "Today", sub: label };
  if (key === addDays(today, 1)) return { main: "Tomorrow", sub: label };
  return { main: label, sub: null };
}

/**
 * Luma-style list: events grouped by day under a quiet date heading, a thin line down the left,
 * and calm rows with the poster on the right. Only transform/opacity animate, on first appearance.
 */
export function Timeline({ items }: { items: FeedItem[] }) {
  const groups: { key: string; items: FeedItem[] }[] = [];
  for (const e of items) {
    const key = dayKey(e.start_at);
    const last = groups[groups.length - 1];
    if (last?.key === key) last.items.push(e);
    else groups.push({ key, items: [e] });
  }
  let index = 0;
  return (
    <div className="flex flex-col gap-8">
      {groups.map((g, gi) => {
        const h = dayHeading(g.key);
        return (
          <section key={`${g.key}-${gi}`} aria-label={h.sub ? `${h.main}, ${h.sub}` : h.main} className="relative pl-5">
            <span className="absolute bottom-0 left-[3px] top-2 w-px bg-line" aria-hidden />
            <span className="absolute left-0 top-[7px] size-[7px] rounded-full bg-text/25" aria-hidden />
            <h2 className="mb-2 flex items-baseline gap-2">
              <span className="headline">{h.main}</span>
              {h.sub && <span className="callout text-text-2">{h.sub}</span>}
            </h2>
            <ul className="flex flex-col">
              {g.items.map((e) => (
                <TimelineRow key={e.id} event={e} index={index++} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function TimelineRow({ event: e, index }: { event: FeedItem; index: number }) {
  const prefetch = usePrefetchEvent();
  const internship = e.event_type === "internship";
  const fit = e.time_fit;
  return (
    <m.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: easeOut, delay: Math.min(index, 8) * 0.03 }}
      className="relative"
    >
      <Link
        to={`/event/${e.id}`}
        onPointerEnter={() => prefetch(e.id)}
        onTouchStart={() => prefetch(e.id)}
        className={`pressable -mx-3 flex gap-4 rounded-[16px] px-3 py-3 outline-none hover:bg-text/[0.03] focus-visible:ring-2 focus-visible:ring-accent`}
      >
        <div className="min-w-0 flex-1">
          <p className="footnote font-medium text-text-2 tnum">{internship ? "Apply by end of day" : formatTimeRange(e.start_at, e.end_at)}</p>
          <h3 className="headline mt-0.5 line-clamp-2">{e.title}</h3>
          {e.organizer_name && <p className="callout text-text-2">By <ClubName name={e.organizer_name} slug={e.organizer_slug} /></p>}
          <p className="callout flex items-center gap-1 text-text-2">
            <MapPin className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">{e.mode === "online" ? (internship ? "Remote" : "Online") : e.venue_name ?? "In person"}</span>
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {internship ? <OrganizerLabel event={e} /> : <Tag>{formatFee(e.fee_inr)}</Tag>}
            {fit?.fits && <Tag tone="success"><CircleCheck className="size-3.5" aria-hidden />Fits your time</Tag>}
          </div>
          {fit && !fit.fits && (
            <p className="footnote mt-1.5 text-text-2">Doesn't fit your free time{fit.reason ? `. ${fit.reason}` : ""}</p>
          )}
        </div>
        <Thumb event={e} className="size-[76px] shrink-0 self-start" />
      </Link>
    </m.li>
  );
}
