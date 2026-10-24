import { CalendarClock, ChevronRight, Plus, Ticket, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/AppShell";
import { Thumb } from "../../components/events/EventCard";
import { Tag } from "../../components/ui/Chip";
import { CountUp } from "../../components/ui/CountUp";
import { formatDayTime } from "../../lib/format";
import { STATUS_CHIP, useOrgEvents, useOrgSummary } from "../../lib/organizer";
import type { OrgEvent } from "../../lib/types";

const TRUST: Record<string, string> = { trusted: "Trusted organizer", verified: "Verified organizer", new: "New organizer" };

export default function OrganizerHome() {
  const { data: summary } = useOrgSummary();
  const { data: events, isPending, isError, refetch } = useOrgEvents();

  return (
    <>
      <PageHeader
        title={summary?.org_name ?? "Your events"}
        subtitle={summary ? TRUST[summary.trust_level] : undefined}
        action={
          <Link to="/organizer/new" className="pressable inline-flex min-h-11 items-center gap-1.5 rounded-[14px] bg-accent px-4 font-semibold text-white">
            <Plus className="size-5" aria-hidden /> <span className="hidden sm:inline">New event</span>
          </Link>
        }
      />

      <div className="mb-8 grid grid-cols-3 gap-3">
        <Tile icon={CalendarClock} label="Upcoming" value={summary?.upcoming} />
        <Tile icon={Ticket} label="Registrations" value={summary?.registrations} />
        <Tile icon={TrendingUp} label="Attendance" value={summary?.attendance_rate != null ? Math.round(summary.attendance_rate * 100) : undefined} suffix="%" />
      </div>

      <h2 className="title-3 mb-3">Events</h2>
      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load your events.</p>
          <button onClick={() => refetch()} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-40 rounded-[22px]" />
      ) : events.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="headline">No events yet.</p>
          <p className="callout mt-1 text-text-2">Drop a poster and we'll fill in the details.</p>
          <Link to="/organizer/new" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent px-5 font-semibold text-white">Create an event</Link>
        </div>
      ) : (
        <ul className="card divide-y divide-line">
          {events.map((e) => <EventRow key={e.id} event={e} />)}
        </ul>
      )}
    </>
  );
}

function Tile({ icon: Icon, label, value, suffix = "" }: { icon: typeof Ticket; label: string; value: number | undefined; suffix?: string }) {
  return (
    <div className="card p-4">
      <Icon className="size-5 text-accent" aria-hidden />
      <p className="title-2 mt-2">{value == null ? "–" : <><CountUp value={value} />{suffix}</>}</p>
      <p className="footnote text-text-2">{label}</p>
    </div>
  );
}

function EventRow({ event: e }: { event: OrgEvent }) {
  const chip = STATUS_CHIP[e.status];
  return (
    <li>
      <Link to={`/organizer/event/${e.id}/edit`} className="flex items-center gap-4 p-4 hover:bg-text/3">
        <Thumb event={{ id: `org-${e.id}`, category: e.form.category, title: e.form.title || "?", poster_url: e.form.poster_url }} className="size-14 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="headline truncate">{e.form.title || "Untitled"}</p>
          <p className="footnote text-text-2 tnum">
            {e.start_at && e.end_at ? formatDayTime(e.start_at, e.end_at) : "No date yet"}
            {e.status === "published" && ` · ${e.seats_taken} registered`}
          </p>
        </div>
        <Tag tone={chip.tone}>{chip.text}</Tag>
        <ChevronRight className="size-5 shrink-0 text-text-2" aria-hidden />
      </Link>
    </li>
  );
}
