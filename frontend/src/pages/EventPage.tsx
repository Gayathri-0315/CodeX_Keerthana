import { m } from "motion/react";
import { ArrowLeft, Bookmark, ChevronRight, MessagesSquare, CalendarPlus, Check, Clock, ExternalLink, Flag, MapPin, MoreHorizontal, Navigation, Share, ShieldCheck, TriangleAlert, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Thumb } from "../components/events/EventCard";
import { Button } from "../components/ui/Button";
import { OrganizerCard } from "../components/events/OrganizerCard";
import { AskEvent } from "../components/events/AskEvent";
import { Tag } from "../components/ui/Chip";
import { Sheet } from "../components/ui/Sheet";
import { useToast } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { useReportEvent } from "../lib/organizer";
import { RegisterAction } from "../components/attendance/RegisterAction";
import { ApplyOnShowUp } from "../components/attendance/ApplyOnShowUp";
import { ClassmatesLine, GoTogetherCard } from "../components/attendance/GoTogether";
import { formatFee, formatLongDate, formatTimeRange } from "../lib/format";
import { easeOut } from "../lib/motion";
import { useEvent, useMe, useSaveEvent } from "../lib/queries";
import { openAuth, showRoleNotice } from "../lib/authModal";
import type { EventDetail } from "../lib/types";
import { useChatEntry } from "../lib/chat";

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
        <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Back to events</Link>
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
            By {e.organizer.slug ? <Link to={`/club/${e.organizer.slug}`} className="font-medium text-accent">{e.organizer.name}</Link> : e.organizer.name}
            {e.organizer.trust_level !== "new" && <> · {e.organizer.trust_label}</>}
          </p>
        )}

        <dl className="card mt-6 divide-y divide-line px-5">
          {e.event_type === "internship" ? (
            <Row icon={Clock} label="Apply by">
              <span className="body">Apply by {formatLongDate(e.start_at)}</span>
              <span className="callout block text-text-2">
                {e.registration_url ? `Applications go to ${siteOf(e.registration_url)}.` : "Apply here on ShowUp; the organizer replies by email."}
              </span>
            </Row>
          ) : (
            <Row icon={Clock} label="When">
              <span className="body">{formatLongDate(e.start_at)}</span>
              <span className="callout block text-text-2 tnum">{formatTimeRange(e.start_at, e.end_at)}</span>
            </Row>
          )}
          <Row icon={MapPin} label="Where">
            {e.mode === "online" ? (
              <span className="body">{e.event_type === "internship" ? "Remote" : "Online"}</span>
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

        {e.registration && ["registered", "promoted_pending", "waitlisted"].includes(e.registration.status) ? (
          <GoTogetherCard registrationId={e.registration.id} companions={e.companions} eventTitle={e.title} />
        ) : (
          <ClassmatesLine c={e.classmates_going} className="mt-4 px-1 callout" />
        )}

        {e.registration && ["registered", "attended"].includes(e.registration.status) && <ChatEntry eventId={e.id} />}

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
        {e.status === "published" && <AskEvent eventId={e.id} />}
        {e.organizer && <OrganizerCard org={e.organizer} />}
      </m.div>

      <ActionBar event={e} />
    </article>
  );
}

function Row({ icon: Icon, label, children }: { icon: typeof Clock; label: string; children: React.ReactNode }) {
  // dl > div > (dt, dd) is the only valid grouping, so the icon lives inside the dd.
  return (
    <div className="py-4">
      <dt className="sr-only">{label}</dt>
      <dd className="flex gap-4">
        <Icon className="mt-0.5 size-5 shrink-0 text-text-2" aria-hidden />
        <div className="min-w-0">{children}</div>
      </dd>
    </div>
  );
}

function ActionBar({ event: e }: { event: EventDetail }) {
  const { data: me } = useMe();
  const guest = !me;
  const student = me?.role === "student";
  const save = useSaveEvent();
  const toast = useToast();
  const [reporting, setReporting] = useState(false);
  const [more, setMore] = useState(false);

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
          <p className="headline tnum">{e.event_type === "internship" ? "Internship" : formatFee(e.fee_inr)}</p>
          {e.match != null && <p className="footnote text-text-2 tnum">{e.match}% match</p>}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <button onClick={() => setMore(true)} aria-label="More actions" aria-haspopup="dialog" className="pressable grid size-11 shrink-0 place-items-center rounded-full bg-text/6 text-accent">
            <MoreHorizontal className="size-5" />
          </button>
          {e.event_type === "internship" ? (
            e.status === "published" && !e.registration_url ? (
              <ApplyOnShowUp event={e} />
            ) : e.status === "published" && e.registration_url && (
              <a href={e.registration_url} target="_blank" rel="noopener noreferrer"
                aria-label={`Apply on ${siteOf(e.registration_url)} (opens in a new tab)`}
                className="pressable inline-flex h-[52px] min-w-0 flex-col items-center justify-center rounded-[14px] bg-accent-fill px-6 text-white">
                <span className="flex items-center gap-2 text-[17px] font-semibold leading-5">Apply <ExternalLink className="size-4" aria-hidden /></span>
                <span className="max-w-[160px] truncate text-[11px] leading-4 text-white/80">on {siteOf(e.registration_url)}</span>
              </a>
            )
          ) : (
            <>
              {guest && e.status === "published" && (
                <Button size="lg" onClick={() => openAuth({ audience: "student", intent: { kind: "register", eventId: e.id } })}>Register</Button>
              )}
              {student && e.status === "published" && (e.fits || e.registration || !e.why_not) && <RegisterAction event={e} />}
              {me?.role === "organizer" && e.status === "published" && (
                <Button size="lg" onClick={() => showRoleNotice("organizer_cannot_register")}>Register</Button>
              )}
            </>
          )}
        </div>
      </div>
      <Sheet open={more} onClose={() => setMore(false)} title={e.title}>
        <div className="flex flex-col gap-1">
          {(guest || student) && (
            <MenuItem
              icon={Bookmark}
              label={e.saved ? "Remove from saved" : "Save"}
              onClick={() => {
                setMore(false);
                if (guest) return openAuth({ audience: "student", intent: { kind: "save", eventId: e.id } });
                save.mutate({ id: e.id, saved: !e.saved }, { onSuccess: () => toast({ tone: "success", title: e.saved ? "Removed from saved" : "Saved" }) });
              }}
            />
          )}
          {student && (
            <a href={`/api/events/${e.id}/ics`} onClick={() => setMore(false)} className="pressable flex min-h-12 items-center gap-3 rounded-[14px] px-3 body hover:bg-text/5">
              <CalendarPlus className="size-5 text-accent" aria-hidden /> Add to my phone calendar
            </a>
          )}
          <MenuItem icon={Share} label="Share" onClick={() => { setMore(false); void share(); }} />
          <MenuItem
            icon={Flag}
            label="Report this event"
            tone="danger"
            onClick={() => {
              setMore(false);
              if (guest) return openAuth({ audience: "student", intent: { kind: "navigate", to: `/event/${e.id}` } });
              setReporting(true);
            }}
          />
        </div>
      </Sheet>
      <ReportSheet eventId={e.id} open={reporting} onClose={() => setReporting(false)} />
    </div>
  );
}

function MenuItem({ icon: Icon, label, onClick, tone }: { icon: typeof Flag; label: string; onClick: () => void; tone?: "danger" }) {
  return (
    <button onClick={onClick} className={`pressable flex min-h-12 items-center gap-3 rounded-[14px] px-3 text-left body hover:bg-text/5 ${tone === "danger" ? "text-danger-text" : ""}`}>
      <Icon className={`size-5 ${tone === "danger" ? "" : "text-accent"}`} aria-hidden /> {label}
    </button>
  );
}

const REPORT_REASONS = [
  "Looks like a scam",
  "Asks for payment in a suspicious way",
  "Wrong date, time or place",
  "Duplicate of another event",
  "Something else",
];

function ReportSheet({ eventId, open, onClose }: { eventId: string; open: boolean; onClose: () => void }) {
  const [reason, setReason] = useState<string | null>(null);
  const report = useReportEvent();
  const toast = useToast();
  return (
    <Sheet open={open} onClose={onClose} title="Report this event">
      <p className="callout mb-3 text-text-2">Tell us what's wrong. Your report is private.</p>
      <div role="radiogroup" aria-label="Reason" className="flex flex-col gap-1">
        {REPORT_REASONS.map((r) => (
          <button
            key={r}
            role="radio"
            aria-checked={reason === r}
            onClick={() => setReason(r)}
            className={`pressable flex min-h-12 items-center justify-between rounded-[14px] px-4 text-left body ${reason === r ? "bg-accent-soft text-accent" : "hover:bg-text/5"}`}
          >
            {r}
            {reason === r && <Check className="size-5" aria-hidden />}
          </button>
        ))}
      </div>
      <Button
        size="lg"
        full
        className="mt-5"
        disabled={!reason}
        loading={report.isPending}
        onClick={() =>
          report.mutate(
            { id: eventId, reason: reason! },
            {
              onSuccess: () => {
                onClose();
                setReason(null);
                toast({ tone: "success", title: "Thanks for reporting", body: "We'll review this event." });
              },
              onError: (err) => toast({ tone: "error", title: "Couldn't send report", body: (err as Error).message }),
            },
          )
        }
      >
        Send report
      </Button>
    </Sheet>
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

/** Registered students get the event's group chat with the host and others going. */
function ChatEntry({ eventId }: { eventId: string }) {
  const { inChat, unread } = useChatEntry(eventId, true);
  if (!inChat) return null;
  return (
    <Link to={`/event/${eventId}/chat`} className="card pressable mt-4 flex min-h-[60px] items-center gap-3 px-5 py-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><MessagesSquare className="size-5" aria-hidden /></span>
      <span className="min-w-0 flex-1">
        <span className="headline block">Group chat</span>
        <span className="footnote block text-text-2">Talk with the host and people going</span>
      </span>
      {unread > 0 && (
        <span className="grid h-6 min-w-6 place-items-center rounded-full bg-danger px-1.5 text-[12px] font-semibold text-white tnum" aria-label={`${unread} unread`}>
          {unread > 9 ? "9+" : unread}
        </span>
      )}
      <ChevronRight className="size-5 text-text-2" aria-hidden />
    </Link>
  );
}

/** "psgtech.ac.in" from a full link, so students see where Apply takes them. */
function siteOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "their website";
  }
}
