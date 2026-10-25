import { m } from "motion/react";
import { ArrowLeft, Download, MessageSquare, Pencil, QrCode, Search, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Tag } from "../../components/ui/Chip";
import { CountUp } from "../../components/ui/CountUp";
import { Segmented } from "../../components/ui/Segmented";
import { Sheet } from "../../components/ui/Sheet";
import { useToast } from "../../components/ui/Toaster";
import { useAnalytics, useCancelEvent, useMessageRegistrants, useRegistrants } from "../../lib/attendance";
import { formatDayTime, formatTime } from "../../lib/format";
import { easeOut } from "../../lib/motion";
import { STATUS_CHIP, useOrgEvent } from "../../lib/organizer";
import type { Analytics, Registrant } from "../../lib/types";

type Filter = "all" | "registered" | "waitlisted" | "attended" | "no_show";
const STATUS_LABEL: Record<string, string> = {
  registered: "Registered", waitlisted: "Waitlist", promoted_pending: "Seat offered", attended: "Checked in", no_show: "No-show",
};

export default function EventManager() {
  const { id = "" } = useParams();
  const event = useOrgEvent(id);
  const analytics = useAnalytics(id);
  const registrants = useRegistrants(id);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [messaging, setMessaging] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const rows = useMemo(() => {
    const all = registrants.data ?? [];
    return all.filter(
      (r) => (filter === "all" || r.status === filter || (filter === "registered" && r.status === "promoted_pending")) && r.name.toLowerCase().includes(q.trim().toLowerCase()),
    );
  }, [registrants.data, filter, q]);

  if (event.isPending) return <div className="skeleton h-96 rounded-[22px]" />;
  if (event.isError || !event.data) {
    return (
      <div className="card p-8 text-center">
        <p className="headline">Couldn't load this event.</p>
        <Link to="/" className="callout mt-2 inline-block text-accent">Back to dashboard</Link>
      </div>
    );
  }
  const e = event.data;
  const chip = STATUS_CHIP[e.status];
  const live = e.status === "published";

  const exportCsv = () => {
    const header = "Name,Status,Waitlist position,Registered at,Checked in at,Show-up likelihood\n";
    const body = (registrants.data ?? [])
      .map((r) => [r.name, STATUS_LABEL[r.status] ?? r.status, r.waitlist_position ?? "", r.registered_at, r.checked_in_at ?? "", r.likelihood ?? ""]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const url = URL.createObjectURL(new Blob([header + body], { type: "text/csv" }));
    Object.assign(document.createElement("a"), { href: url, download: `${e.form.title.replace(/\W+/g, "-").toLowerCase()}-registrations.csv` }).click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="pb-16">
      <Link to="/" className="pressable -ml-2 mb-3 inline-flex min-h-11 items-center gap-1 rounded-full px-2 callout font-medium text-accent">
        <ArrowLeft className="size-5" aria-hidden /> Dashboard
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Tag tone={chip.tone}>{chip.text}</Tag>
          <h1 className="title-1 mt-2">{e.form.title}</h1>
          {e.start_at && e.end_at && <p className="callout mt-1 text-text-2 tnum">{formatDayTime(e.start_at, e.end_at)}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {live && (
            <Link to={`/organizer/event/${id}/checkin`} className="pressable inline-flex min-h-11 items-center gap-2 rounded-[14px] bg-accent px-4 font-semibold text-white">
              <QrCode className="size-5" aria-hidden /> Check-in
            </Link>
          )}
          <Link to={`/organizer/event/${id}/edit`} className="pressable inline-flex min-h-11 items-center gap-2 rounded-[14px] bg-accent-soft px-4 font-semibold text-accent">
            <Pencil className="size-4" aria-hidden /> Edit
          </Link>
        </div>
      </div>

      {analytics.data && <TurnoutCard a={analytics.data} />}

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="title-3">Registrations</h2>
          <div className="flex flex-wrap gap-2">
            {live && <Button size="sm" variant="secondary" onClick={() => setMessaging(true)}><MessageSquare className="size-4" aria-hidden /> Message</Button>}
            <Button size="sm" variant="secondary" onClick={exportCsv} disabled={!registrants.data?.length}><Download className="size-4" aria-hidden /> Export CSV</Button>
            {live && <Button size="sm" variant="danger" onClick={() => setCancelling(true)}><XCircle className="size-4" aria-hidden /> Cancel event</Button>}
          </div>
        </div>
        <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
            <input
              type="search"
              aria-label="Search registrants"
              placeholder="Search by name"
              value={q}
              onChange={(ev) => setQ(ev.target.value)}
              className="h-11 w-full rounded-[14px] bg-surface pl-11 pr-4 body shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
            />
          </div>
          <div className="no-scrollbar overflow-x-auto">
            <Segmented
              label="Filter"
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "All" }, { value: "registered", label: "Registered" }, { value: "waitlisted", label: "Waitlist" },
                { value: "attended", label: "Checked in" }, { value: "no_show", label: "No-show" },
              ]}
            />
          </div>
        </div>
        {registrants.isPending ? (
          <div className="skeleton h-40 rounded-[22px]" />
        ) : rows.length === 0 ? (
          <div className="card p-6 text-center callout text-text-2">{registrants.data?.length ? "Nobody matches that filter." : "No registrations yet."}</div>
        ) : (
          <ul className="card divide-y divide-line">
            {rows.map((r) => <RegistrantRow key={r.id} r={r} />)}
          </ul>
        )}
        <p className="footnote mt-3 text-text-2">Show-up likelihood is a planning estimate from simple rules, not a promise. Attendee lists are only visible to you.</p>
      </section>

      <MessageSheet eventId={id} open={messaging} onClose={() => setMessaging(false)} />
      <CancelSheet eventId={id} open={cancelling} onClose={() => setCancelling(false)} onDone={() => event.refetch()} />
    </div>
  );
}

function TurnoutCard({ a }: { a: Analytics }) {
  const scale = Math.max(a.capacity ?? 0, a.registered, a.expected_high, a.actual, 1);
  const pct = (v: number) => `${(v / scale) * 100}%`;
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="title-3">Predicted vs actual</h2>
        <p className="footnote text-text-2 tnum">
          {a.registered} registered{a.capacity ? ` of ${a.capacity}` : ""}{a.waitlisted ? ` · ${a.waitlisted} waiting` : ""}
        </p>
      </div>
      <div className="mt-5 flex flex-col gap-5">
        <Bar label="Expected" value={<><CountUp value={Math.round(a.expected)} /> <span className="footnote font-normal text-text-2">({a.expected_low} to {a.expected_high})</span></>}>
          <div className="absolute inset-y-0 rounded-full bg-accent/20" style={{ left: pct(a.expected_low), width: `calc(${pct(a.expected_high)} - ${pct(a.expected_low)})` }} />
          <m.div className="absolute inset-y-0 left-0 w-full origin-left rounded-full bg-accent" initial={{ scaleX: 0 }} animate={{ scaleX: a.expected / scale }} transition={{ duration: 0.7, ease: easeOut }} />
        </Bar>
        <Bar label="Checked in" value={<CountUp value={a.actual} />}>
          <m.div className="absolute inset-y-0 left-0 w-full origin-left rounded-full bg-success" initial={{ scaleX: 0 }} animate={{ scaleX: a.actual / scale }} transition={{ duration: 0.7, ease: easeOut }} />
        </Bar>
      </div>
      <p className="footnote mt-4 text-text-2">Expected is the sum of each person's show-up likelihood (planning estimate), with a rough 80% range.</p>
    </div>
  );
}

function Bar({ label, value, children }: { label: string; value: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="callout text-text-2">{label}</span>
        <span className="headline tnum">{value}</span>
      </div>
      <div className="relative h-3 overflow-hidden rounded-full bg-text/6">{children}</div>
    </div>
  );
}

function RegistrantRow({ r }: { r: Registrant }) {
  const [open, setOpen] = useState(false);
  const tone = r.likelihood == null ? "bg-text/20" : r.likelihood >= 0.7 ? "bg-success" : r.likelihood >= 0.45 ? "bg-warning" : "bg-danger";
  return (
    <li className="px-4 py-3">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={r.likelihood == null ? "No estimate" : `Show-up likelihood ${Math.round(r.likelihood * 100)}%, show reasons`}
          title={r.reasons.join("\n")}
          className="grid size-11 shrink-0 place-items-center rounded-full hover:bg-text/5"
          disabled={r.likelihood == null}
        >
          <span className={`size-3 rounded-full ${tone}`} />
        </button>
        <div className="min-w-0 flex-1">
          <p className="body truncate">{r.name}</p>
          <p className="footnote text-text-2 tnum">
            {r.status === "waitlisted" ? `Waitlist #${r.waitlist_position}` : STATUS_LABEL[r.status] ?? r.status}
            {r.checked_in_at && ` at ${formatTime(r.checked_in_at)}`}
            {r.external && " · registered on your site"}
          </p>
        </div>
        {r.likelihood != null && <span className="callout text-text-2 tnum">{Math.round(r.likelihood * 100)}%</span>}
      </div>
      {open && (
        <ul className="footnote ml-14 mt-1 list-disc pl-4 text-text-2">
          {r.reasons.length ? r.reasons.map((x) => <li key={x}>{x}</li>) : <li>Baseline estimate (70%)</li>}
        </ul>
      )}
    </li>
  );
}

function MessageSheet({ eventId, open, onClose }: { eventId: string; open: boolean; onClose: () => void }) {
  const [text, setText] = useState("");
  const send = useMessageRegistrants(eventId);
  const toast = useToast();
  return (
    <Sheet open={open} onClose={onClose} title="Message registrants">
      <p className="callout text-text-2">Goes to everyone registered or waiting, in the app and on their alert channels.</p>
      <textarea
        aria-label="Message"
        rows={4}
        maxLength={200}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. Room changed to Hall B. Bring your laptop charger."
        className="mt-3 w-full rounded-[14px] bg-surface-2 p-3 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
      />
      <p className="footnote text-right text-text-2 tnum">{text.length}/200</p>
      <Button
        size="lg"
        full
        className="mt-3"
        disabled={text.trim().length < 3}
        loading={send.isPending}
        onClick={() =>
          send.mutate(text.trim(), {
            onSuccess: (r) => {
              onClose();
              setText("");
              toast({ tone: "success", title: "Message sent", body: `${r.sent} ${r.sent === 1 ? "person" : "people"} notified.` });
            },
            onError: (e) => toast({ tone: "error", title: "Couldn't send", body: (e as Error).message }),
          })
        }
      >
        Send message
      </Button>
    </Sheet>
  );
}

function CancelSheet({ eventId, open, onClose, onDone }: { eventId: string; open: boolean; onClose: () => void; onDone: () => void }) {
  const cancel = useCancelEvent(eventId);
  const toast = useToast();
  return (
    <Sheet open={open} onClose={onClose} title="Cancel this event?">
      <p className="callout text-text-2">Everyone registered or waiting gets an alert right away. This can't be undone.</p>
      <div className="mt-6 flex flex-col gap-2">
        <Button
          variant="danger"
          size="lg"
          full
          loading={cancel.isPending}
          onClick={() =>
            cancel.mutate(undefined, {
              onSuccess: (r) => {
                onClose();
                onDone();
                toast({ tone: "success", title: "Event cancelled", body: `${r.notified} ${r.notified === 1 ? "person was" : "people were"} told.` });
              },
              onError: (e) => toast({ tone: "error", title: "Couldn't cancel", body: (e as Error).message }),
            })
          }
        >
          Cancel event
        </Button>
        <Button variant="quiet" size="lg" full onClick={onClose}>Keep it</Button>
      </div>
    </Sheet>
  );
}
