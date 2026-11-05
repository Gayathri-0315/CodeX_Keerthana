import { Clock, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import { formatFee, formatWhen } from "../../lib/format";
import { usePrefetchEvent } from "../../lib/queries";
import type { FeedItem } from "../../lib/types";
import { Tag } from "../ui/Chip";
import { Thumb } from "../events/EventCard";
import { ClubName } from "../events/ClubName";

/** A calm card for guests: no personal fit, just what, when, where and how much. */
export function PublicEventCard({ event }: { event: FeedItem }) {
  const prefetch = usePrefetchEvent();
  return (
    <Link
      to={`/event/${event.id}`}
      onPointerEnter={() => prefetch(event.id)}
      onTouchStart={() => prefetch(event.id)}
      className="pressable liftable card flex h-full gap-4 p-4 outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <Thumb event={event} className="size-[72px] shrink-0" />
      <div className="min-w-0 flex-1">
        <h3 className="headline line-clamp-2">{event.title}</h3>
        {event.organizer_name && <p className="footnote mt-0.5 text-text-2"><ClubName name={event.organizer_name} slug={event.organizer_slug} /></p>}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Tag tone="accent"><Clock className="size-3.5" aria-hidden />{formatWhen(event)}</Tag>
          <Tag><MapPin className="size-3.5" aria-hidden />{event.mode === "online" ? (event.event_type === "internship" ? "Remote" : "Online") : event.venue_name ?? "In person"}</Tag>
          {event.event_type === "internship" ? <OrganizerLabel event={event} /> : <Tag>{formatFee(event.fee_inr)}</Tag>}
        </div>
      </div>
    </Link>
  );
}

export function PublicEventCardSkeleton() {
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

/** Every internship carries a clear label saying who checked the organizer. */
export function OrganizerLabel({ event }: { event: Pick<FeedItem, "verification_label"> }) {
  if (event.verification_label === "organizer_verified") return <Tag tone="success">Verified organizer</Tag>;
  if (event.verification_label === "details_reviewed") return <Tag>Reviewed by ShowUp</Tag>;
  return <Tag tone="warning">Unverified</Tag>;
}
