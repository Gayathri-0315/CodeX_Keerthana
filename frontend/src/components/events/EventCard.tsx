import { animate, m, useMotionValue, useTransform, type PanInfo } from "motion/react";
import { Bookmark, CircleCheck, Clock, MapPin, Sparkles, TriangleAlert } from "lucide-react";
import { useRef, type MouseEvent } from "react";
import { Link } from "react-router-dom";
import { Tag } from "../ui/Chip";
import { formatFee, formatKm, formatWhen } from "../../lib/format";
import { OrganizerLabel } from "../landing/PublicEventCard";
import { easeOut, haptic, spring } from "../../lib/motion";
import { usePrefetchEvent } from "../../lib/queries";
import type { FeedItem } from "../../lib/types";
import { RegisterAction } from "../attendance/RegisterAction";
import { ClassmatesLine } from "../attendance/GoTogether";
import { ClubName } from "./ClubName";

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
  Internship: ["#30b0c7", "#5856d6"],
  Competition: ["#ff375f", "#ff9f0a"],
};

/** Gradient by event type first (item 12), then by the poster's own category text. */
const TYPE_KEY: Record<string, string> = {
  workshop: "Workshop", meetup: "Meetup", hackathon: "Hackathon", conference: "Conference", webinar: "Webinar",
  internship: "Internship", competition: "Competition",
};

/** Poster when there is one, otherwise a category gradient. Shares a layoutId with the detail hero. */
export function Thumb({ event, className = "", large = false }: { event: Pick<FeedItem, "id" | "category" | "title" | "poster_url"> & { event_type?: string }; className?: string; large?: boolean }) {
  const [a, b] = GRADIENTS[TYPE_KEY[event.event_type ?? ""] ?? event.category] ?? GRADIENTS[event.category] ?? ["#636366", "#aeaeb2"];
  return (
    <m.div
      layoutId={`thumb-${event.id}`}
      transition={spring}
      aria-hidden
      className={`grid place-items-center overflow-hidden text-white ${large ? "rounded-[22px]" : "rounded-[16px]"} ${className}`}
      style={{ background: `linear-gradient(135deg, ${a}, ${b})` }}
    >
      {event.poster_url ? (
        <img src={event.poster_url} alt="" className="size-full object-cover" loading="lazy" decoding="async" />
      ) : (
        <span className={`font-semibold tracking-tight opacity-90 ${large ? "text-[64px]" : "text-[26px]"}`}>{event.title.trim()[0]}</span>
      )}
    </m.div>
  );
}

type Props = {
  event: FeedItem;
  index: number;
  onToggleSave: (e: FeedItem) => void;
  onDismiss?: (e: FeedItem) => void;
  onRemindSimilar?: (e: FeedItem) => void;
  /** Explore shows every event with a time-fit badge instead of reasons and the match bar. */
  variant?: "feed" | "explore";
};

export function EventCard({ event, index, onToggleSave, onDismiss, onRemindSimilar, variant = "feed" }: Props) {
  const explore = variant === "explore";
  const prefetch = usePrefetchEvent();
  const x = useMotionValue(0);
  const revealOpacity = useTransform(x, [-140, -40, 0], [1, 0.4, 0]);
  const dragged = useRef(false);
  const muted = !explore && event.almost && !event.fits;

  const onDragEnd = (_: unknown, info: PanInfo) => {
    if (onDismiss && (info.offset.x < -120 || info.velocity.x < -700)) {
      haptic();
      animate(x, -window.innerWidth, { duration: 0.22, ease: easeOut }).then(() => onDismiss(event));
    } else {
      animate(x, 0, { type: "spring", stiffness: 320, damping: 30 });
    }
    window.setTimeout(() => (dragged.current = false), 0);
  };

  const guardClick = (e: MouseEvent) => {
    if (dragged.current) e.preventDefault(); // a swipe is not a tap
  };

  return (
    <m.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: easeOut, delay: Math.min(index, 8) * 0.03 }}
      className="relative"
    >
      {onDismiss && (
        <m.div style={{ opacity: revealOpacity }} className="absolute inset-0 flex items-center justify-end rounded-[22px] bg-danger/15 pr-6 callout font-semibold text-danger-text" aria-hidden>
          Not for me
        </m.div>
      )}
      <m.article
        style={{ x }}
        drag={onDismiss ? "x" : false}
        dragDirectionLock
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={{ left: 0.9, right: 0.05 }}
        onDragStart={() => (dragged.current = true)}
        onDragEnd={onDragEnd}
        className="card relative overflow-hidden"
      >
        <Link
          to={`/event/${event.id}`}
          onClick={guardClick}
          onPointerEnter={() => prefetch(event.id)}
          onTouchStart={() => prefetch(event.id)}
          draggable={false}
          className="flex gap-4 p-4 pr-14 outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset rounded-[22px]"
        >
          <Thumb event={event} className={`size-[72px] shrink-0 ${muted ? "opacity-70 saturate-50" : ""}`} />
          <div className="min-w-0 flex-1">
            <h3 className="headline line-clamp-2">{event.title}</h3>
            <p className="footnote mt-0.5 text-text-2"><ClubName name={event.organizer_name} slug={event.organizer_slug} /></p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Tag tone={muted ? "neutral" : "accent"}><Clock className="size-3.5" aria-hidden />{formatWhen(event)}</Tag>
              <Tag><MapPin className="size-3.5" aria-hidden />{formatKm(event.distance_km)}</Tag>
              {event.event_type === "internship" ? <OrganizerLabel event={event} /> : <Tag>{formatFee(event.fee_inr)}</Tag>}
              {event.waitlist && <Tag tone="warning">Waitlist</Tag>}
              {event.event_type !== "internship" && event.verification_label === "unverified" && <Tag tone="warning">Unverified</Tag>}
            </div>
            {explore && event.time_fit && (
              <p className={`footnote mt-2 flex items-start gap-1.5 ${event.time_fit.fits ? "text-success-text" : "text-text-2"}`}>
                {event.time_fit.fits ? <CircleCheck className="mt-px size-4 shrink-0" aria-hidden /> : <TriangleAlert className="mt-px size-4 shrink-0" aria-hidden />}
                <span>
                  <span className="font-medium">{event.time_fit.fits ? "Fits your time" : "Doesn't fit your free time"}</span>
                  {!event.time_fit.fits && event.time_fit.reason && <span>. {event.time_fit.reason}</span>}
                </span>
              </p>
            )}
            {!explore && !muted && event.card_reasons.length > 0 && (
              <ul className="mt-2.5 flex flex-col gap-1" aria-label="Why it fits">
                {event.card_reasons.map((r) => (
                  <li key={r} className="footnote flex items-start gap-1.5 text-text-2">
                    <Sparkles className="mt-px size-3.5 shrink-0 text-accent" aria-hidden />
                    {r}
                  </li>
                ))}
              </ul>
            )}
            {!muted && <ClassmatesLine c={event.classmates_going} className="mt-1.5" />}
            {!explore && event.clash && (
              <p className="footnote mt-2 flex items-start gap-1.5 text-warning-text">
                <TriangleAlert className="mt-px size-4 shrink-0" aria-hidden />
                {event.clash}
              </p>
            )}
          </div>
        </Link>

        <button
          onClick={() => onToggleSave(event)}
          aria-pressed={event.saved}
          aria-label={event.saved ? `Unsave ${event.title}` : `Save ${event.title}`}
          className="pressable absolute right-2 top-2 grid size-11 place-items-center rounded-full text-text-2 hover:text-accent"
        >
          <Bookmark className={`size-5 ${event.saved ? "fill-accent text-accent" : ""}`} />
        </button>

        {event.fits && !muted && event.event_type !== "internship" && (
          <div className="-mt-1 flex justify-end px-4 pb-3">
            <RegisterAction event={event} compact />
          </div>
        )}

        {muted && onRemindSimilar && (
          <div className="-mt-2 px-4 pb-3 pl-[104px]">
            <button onClick={() => onRemindSimilar(event)} className="min-h-11 callout font-medium text-accent">
              Remind me of similar events
            </button>
          </div>
        )}

        {!explore && event.match != null && !muted && (
          <div className="h-[3px] w-full bg-text/5" role="meter" aria-valuenow={event.match} aria-valuemin={0} aria-valuemax={100} aria-label="Match">
            <m.div
              className="h-full origin-left bg-accent-fill"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: event.match / 100 }}
              transition={{ duration: 0.6, ease: easeOut, delay: 0.1 + Math.min(index, 8) * 0.03 }}
            />
          </div>
        )}
      </m.article>
    </m.div>
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
        <div className="skeleton h-3 w-1/2 rounded-full" />
      </div>
    </div>
  );
}
