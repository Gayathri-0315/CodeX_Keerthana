import { m } from "motion/react";
import { ArrowLeft, Bookmark, Check, Clock, MapPin, Navigation, Share, ShieldCheck, TriangleAlert, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Thumb } from "../components/events/EventCard";
import { Button } from "../components/ui/Button";
import { Tag } from "../components/ui/Chip";
import { useToast } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { formatFee, formatLongDate, formatTimeRange } from "../lib/format";
import { easeOut } from "../lib/motion";
import { useEvent, useSaveEvent } from "../lib/queries";
import type { EventDetail } from "../lib/types";

const LABEL: Record<EventDetail["verification_label"], { text: string; tone: "success" | "neutral" | "warning" }> = {
  organizer_verified: { text: "Verified organizer", tone: "success" },
  details_reviewed: { text: "Details reviewed", tone: "neutral" },
  unverified: { text: "Unverified", tone: "warning" },
};

export default function EventPage() {
  const { id = "" } = useParams();
  const { data: e, isPending, error } = useEvent(id);
  const navigate = useNavigate();
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate("/"));

  if (isPending) return <DetailSkeleton />;
  if (error || !e) {
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <div className="card mx-auto mt-8 max-w-md p-8 text-center">
        <p className="headline">{missing ? "This event isn't available." : "Couldn't load this event."}</p>
        <p className="callout mt-1 text-text-2">{missing ? "It may have been removed by the organizer." : "Check your connection, then try again."}</p>
        <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent px-5 font-semibold text-white">Back to events</Link>
      </div>
    );
  }

  const label = LABEL[e.verification_label];
  return (
    <article className="mx-auto max-w-2xl pb-32">
      <button onClick={back} className="pressable -ml-2 mb-3 inline-flex min-h-11 items-center gap-1 rounded-full px-2 callout font-medium text-accent">
        <ArrowLeft className="size-5" aria-hidden /> Back
      </button>

      <Thumb event={e} large className={`w-full ${e.poster_url ? "aspect-[16/9]" : "aspect-[16/9] sm:aspect-[5/2]"}`} />

      <m.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: easeOut, delay: 0.05 }}>
        <div className="mt-5 flex flex-wrap gap-1.5">
          <Tag tone={label.tone}>{e.verification_label === "organizer_verified" && <ShieldCheck className="size-3.5" aria-hidden />}{label.text}</Tag>
          {e.waitlist && <Tag tone="warning">Waitlist</Tag>}
          {e.status === "cancelled" && <Tag tone="warning">Cancelled</Tag>}
        </div>
        <h1 className="title-1 mt-3">{e.title}</h1>
        {e.organizer && (
          <p className="callout mt-1 text-text-2">
            By {e.organizer.name}
            {e.organizer.trust_level !== "new" && <> · {e.organizer.trust_label}</>}
          </p>
        )}

        <dl className="card mt-6 divide-y divide-line px-5">
          <Row icon={Clock} label="When">
            <span className="body">{formatLongDate(e.start_at)}</span>
            <span className="callout block text-text-2 tnum">{formatTimeRange(e.start_at, e.end_at)}</span>
          </Row>
          <Row icon={MapPin} label="Where">
            {e.mode === "online" ? (
              <span className="body">Online</span>
            ) : (
              <>
                <span className="body">{e.venue_name}</span>
                {e.address && <span className="callout block text-text-2">{e.address}</span>}
                {e.distance_km != null && <span className="callout block text-text-2">{Math.max(1, Math.round(e.distance_km))} km, about {e.travel_min} min away</span>}
                {e.maps_url && (
                  <a href={e.maps_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex min-h-11 items-center gap-1 callout font-medium text-accent">
                    <Navigation className="size-4" aria-hidden /> Directions
                  </a>
                )}
              </>
            )}
          </Row>
          {e.capacity != null && (
            <Row icon={Users} label="Seats">
              <span className="body tnum">{Math.min(e.seats_taken, e.capacity)} of {e.capacity} seats taken</span>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-text/8">
                <m.div
                  className={`h-full origin-left rounded-full ${e.seats_taken >= e.capacity ? "bg-warning" : "bg-success"}`}
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: Math.min(1, e.seats_taken / e.capacity) }}
                  transition={{ duration: 0.6, ease: easeOut, delay: 0.15 }}
                />
              </div>
            </Row>
          )}
          {e.eligibility_text && (
            <Row icon={ShieldCheck} label="Who can join">
              <span className="body">{e.eligibility_text}</span>
            </Row>
          )}
        </dl>

        {(e.clash || e.why_not) && (
          <p className="callout mt-6 flex items-start gap-2 rounded-[14px] bg-warning/12 p-4 text-warning-text">
            <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
            {e.clash ?? e.why_not}
          </p>
        )}

        {e.reasons.length > 0 && (
          <section className="mt-8">
            <h2 className="title-3">Why this matches you</h2>
            <ul className="mt-3 flex flex-col gap-2.5">
              {e.reasons.map((r) => (
                <li key={r} className="body flex items-start gap-3">
                  <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-success/15 text-success-text">
                    <Check className="size-4" strokeWidth={2.5} aria-hidden />
                  </span>
                  {r}
                </li>
              ))}
            </ul>
          </section>
        )}

        {e.description && (
          <section className="mt-8">
            <h2 className="title-3">About</h2>
            <p className="body mt-2 max-w-[65ch] whitespace-pre-line text-text-2">{e.description}</p>
          </section>
        )}
      </m.div>

      <ActionBar event={e} />
    </article>
  );
}

function Row({ icon: Icon, label, children }: { icon: typeof Clock; label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 py-4">
      <Icon className="mt-0.5 size-5 shrink-0 text-text-2" aria-hidden />
      <div className="min-w-0">
        <dt className="sr-only">{label}</dt>
        <dd>{children}</dd>
      </div>
    </div>
  );
}

function ActionBar({ event: e }: { event: EventDetail }) {
  const save = useSaveEvent();
  const toast = useToast();

  const share = async () => {
    const url = `${window.location.origin}/event/${e.id}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: e.title, url });
      } else {
        await navigator.clipboard.writeText(url);
        toast({ tone: "success", title: "Link copied" });
      }
    } catch {
      /* the user closed the share sheet */
    }
  };

  return (
    <div className="glass safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-line">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div>
          <p className="headline tnum">{formatFee(e.fee_inr)}</p>
          {e.match != null && <p className="footnote text-text-2 tnum">{e.match}% match</p>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={share} aria-label="Share" className="pressable grid size-11 place-items-center rounded-full bg-text/6 text-accent">
            <Share className="size-5" />
          </button>
          <Button
            variant={e.saved ? "secondary" : "primary"}
            onClick={() =>
              save.mutate(
                { id: e.id, saved: !e.saved },
                { onSuccess: () => toast({ tone: "success", title: e.saved ? "Removed from saved" : "Saved" }) },
              )
            }
            aria-pressed={e.saved}
          >
            <Bookmark className={`size-5 ${e.saved ? "fill-current" : ""}`} aria-hidden />
            {e.saved ? "Saved" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-2xl" aria-busy="true">
      <div className="mb-3 h-11" />
      <div className="skeleton aspect-[16/9] w-full rounded-[22px]" />
      <div className="skeleton mt-6 h-8 w-3/4 rounded-full" />
      <div className="skeleton mt-3 h-4 w-1/3 rounded-full" />
      <div className="skeleton mt-6 h-40 w-full rounded-[22px]" />
    </div>
  );
}
