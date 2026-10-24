import { m } from "motion/react";
import { Clock, MapPin, TriangleAlert } from "lucide-react";
import { Tag } from "../ui/Chip";
import { formatDayTime, formatFee, formatKm } from "../../lib/format";
import { easeOut } from "../../lib/motion";
import type { EventSummary } from "../../lib/types";

const GRADIENTS: Record<string, [string, string]> = {
  Workshop: ["#0071e3", "#5ac8fa"],
  Meetup: ["#af52de", "#ff2d55"],
  Hackathon: ["#ff9f0a", "#ff375f"],
  Conference: ["#5856d6", "#0a84ff"],
  Webinar: ["#30b0c7", "#34c759"],
  Volunteering: ["#34c759", "#a2d729"],
  Music: ["#ff375f", "#bf5af2"],
  Sports: ["#ff9500", "#ffcc00"],
  Photography: ["#8e8e93", "#5ac8fa"],
};

export function Thumb({ category, title, className = "" }: { category: string; title: string; className?: string }) {
  const [a, b] = GRADIENTS[category] ?? ["#636366", "#aeaeb2"];
  return (
    <div
      aria-hidden
      className={`grid place-items-center overflow-hidden rounded-[16px] text-white ${className}`}
      style={{ background: `linear-gradient(135deg, ${a}, ${b})` }}
    >
      <span className="text-[26px] font-semibold tracking-tight opacity-90">{title.trim()[0]}</span>
    </div>
  );
}

export function EventCard({ event, index }: { event: EventSummary; index: number }) {
  return (
    <m.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: easeOut, delay: Math.min(index, 8) * 0.03 }}
      className={`card flex gap-4 p-4 ${event.almost ? "opacity-80" : ""}`}
    >
      <Thumb category={event.category} title={event.title} className="size-[72px] shrink-0" />
      <div className="min-w-0 flex-1">
        <h3 className="headline line-clamp-2">{event.title}</h3>
        <p className="footnote mt-0.5 text-text-2">{event.organizer_name}</p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Tag tone="accent"><Clock className="size-3.5" aria-hidden />{formatDayTime(event.start_at, event.end_at)}</Tag>
          <Tag><MapPin className="size-3.5" aria-hidden />{formatKm(event.distance_km)}</Tag>
          <Tag>{formatFee(event.fee_inr)}</Tag>
          {event.waitlist && <Tag tone="warning">Waitlist</Tag>}
          {event.verification_label === "unverified" && <Tag tone="warning">Unverified</Tag>}
        </div>
        {event.almost && event.reason && (
          <p className="footnote mt-2 flex items-start gap-1.5 text-warning-text">
            <TriangleAlert className="mt-px size-4 shrink-0" aria-hidden />
            {event.reason}
          </p>
        )}
      </div>
    </m.article>
  );
}

export function EventCardSkeleton() {
  return (
    <div className="card flex gap-4 p-4" aria-hidden>
      <div className="skeleton size-[72px] shrink-0 rounded-[16px]" />
      <div className="flex-1 space-y-2 pt-1">
        <div className="skeleton h-4 w-3/4 rounded-full" />
        <div className="skeleton h-3 w-1/3 rounded-full" />
        <div className="skeleton h-6 w-2/3 rounded-full" />
      </div>
    </div>
  );
}
