import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ExternalLink, Mail, Phone, Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Tag } from "../../components/ui/Chip";
import { Segmented } from "../../components/ui/Segmented";
import { Sheet } from "../../components/ui/Sheet";
import { api } from "../../lib/api";
import { formatFee, formatWhen } from "../../lib/format";
import { STATUS_CHIP } from "../../lib/organizer";

type Person = {
  id: string; name: string; email: string; college: string | null; home_area: string | null; skill_level: string | null;
  department: string | null; year: string | null; kind: string | null; interests: string[]; joined: string | null; last_active: string | null;
};
type AdminEvent = {
  id: string; title: string; status: string; event_type: string; mode: string; venue_name: string | null; start_at: string; end_at: string;
  fee_inr: number; capacity: number | null; organizer: string | null; registered: number; waitlisted: number; attended: number; applications: number;
};
type Reg = Person & { status: string; waitlist_position: number | null; registered_at: string; checked_in_at: string | null; with_friends: boolean };
type App = Person & { status: string; note: string; link: string | null; applied_at: string };
type StudentRow = { id: string; name: string; email: string; college: string | null; department: string | null; year: string | null;
  joined: string; registrations: number; attended: number };
type StudentDetail = Person & { max_distance_km: number | null; budget_max_inr: number | null; following: string[];
  history: { event_id: string; title: string; organizer: string | null; start_at: string; status: string; checked_in_at: string | null }[];
  applications: { event_id: string; title: string; status: string; applied_at: string }[] };
export type OrganizerDetail = {
  id: string; name: string; slug: string | null; trust_level: string; org_type: string | null; college_or_company: string | null; city: string | null;
  bio: string | null; phone: string | null; website: string | null; instagram: string | null; linkedin: string | null; faculty_name: string | null;
  faculty_email: string | null; email_domain: string; contact_name: string | null; email: string | null; joined: string | null;
  last_active: string | null; followers: number; attendance_rate: number | null; events: AdminEvent[];
};

const REG_CHIP: Record<string, { text: string; tone: "neutral" | "accent" | "warning" | "success" }> = {
  registered: { text: "Registered", tone: "accent" },
  promoted_pending: { text: "Seat offered", tone: "accent" },
  attended: { text: "Attended", tone: "success" },
  no_show: { text: "Didn't come", tone: "warning" },
  waitlisted: { text: "Waitlist", tone: "neutral" },
  cancelled: { text: "Cancelled", tone: "neutral" },
  submitted: { text: "Applied", tone: "accent" },
  shortlisted: { text: "Shortlisted", tone: "success" },
  declined: { text: "Declined", tone: "neutral" },
};
// Timestamps -> "6 Nov 2026" (India time).
const shortDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
const join = (xs: (string | null | undefined | false)[]) => xs.filter(Boolean).join(" · ");
const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function useDebounced(text: string) {
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = window.setTimeout(() => setQ(text.trim()), 250);
    return () => window.clearTimeout(t);
  }, [text]);
  return q;
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="relative mb-4 block">
      <span className="sr-only">{placeholder}</span>
      <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
      <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} maxLength={100}
        className="h-12 w-full rounded-[14px] bg-surface pl-11 pr-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]" />
    </label>
  );
}

function ListState({ isError, isPending, empty, refetch, children }: { isError: boolean; isPending: boolean; empty: boolean; refetch: () => void; children: ReactNode }) {
  if (isError) return (
    <div className="card p-6 text-center">
      <p className="headline">Couldn't load this.</p>
      <button onClick={refetch} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
    </div>
  );
  if (isPending) return <div className="skeleton h-48 rounded-[22px]" />;
  if (empty) return <div className="card p-8 text-center"><p className="headline">Nothing matches.</p></div>;
  return <>{children}</>;
}

/** A tappable row: title, a line of details, and a chevron. */
function Row({ onClick, title, tag, lines }: { onClick: () => void; title: string; tag?: ReactNode; lines: string[] }) {
  return (
    <li>
      <button onClick={onClick} className="pressable flex w-full items-center gap-3 py-3.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2"><span className="headline">{title}</span>{tag}</span>
          {lines.filter(Boolean).map((l, i) => <span key={i} className="footnote mt-0.5 block break-words text-text-2 tnum">{l}</span>)}
        </span>
        <ChevronRight className="size-5 shrink-0 text-text-2" aria-hidden />
      </button>
    </li>
  );
}

const eventCounts = (e: AdminEvent) => e.event_type === "internship"
  ? count(e.applications, "application")
  : join([`${e.registered}${e.capacity ? `/${e.capacity}` : ""} registered`, e.waitlisted > 0 && `${e.waitlisted} waitlist`, e.attended > 0 && `${e.attended} attended`]);

function EventRow({ e, onOpen, showOrg = true }: { e: AdminEvent; onOpen: (id: string) => void; showOrg?: boolean }) {
  const chip = STATUS_CHIP[e.status] ?? { text: e.status, tone: "neutral" as const };
  return <Row onClick={() => onOpen(e.id)} title={e.title} tag={<Tag tone={chip.tone}>{chip.text}</Tag>}
    lines={[join([showOrg && e.organizer, formatWhen(e)]), eventCounts(e)]} />;
}

/** Every event; tap one to see who registered. */
export function EventsAdmin({ initialWhen = "upcoming" }: { initialWhen?: "upcoming" | "past" | "all" }) {
  const [text, setText] = useState("");
  const q = useDebounced(text);
  const [when, setWhen] = useState<"upcoming" | "past" | "all">(initialWhen);
  const [open, setOpen] = useState<string | null>(null);
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["admin", "events", when, q],
    queryFn: () => api<{ items: AdminEvent[] }>(`/admin/events?when=${when}${q ? `&q=${encodeURIComponent(q)}` : ""}`).then((r) => r.items),
    placeholderData: (prev) => prev,
  });
  return (
    <section aria-label="Events">
      <SearchBox value={text} onChange={setText} placeholder="Search events or clubs" />
      <Segmented label="Which events" className="mb-4" value={when} onChange={setWhen}
        options={[{ value: "upcoming", label: "Upcoming" }, { value: "past", label: "Past" }, { value: "all", label: "All" }]} />
      <ListState isError={isError} isPending={isPending} empty={!data?.length} refetch={refetch}>
        <ul className="card divide-y divide-line px-5">{data?.map((e) => <EventRow key={e.id} e={e} onOpen={setOpen} />)}</ul>
      </ListState>
      <EventPeopleSheet id={open} onClose={() => setOpen(null)} />
    </section>
  );
}

function Contact({ email, phone }: { email?: string | null; phone?: string | null }) {
  return (
    <span className="flex flex-wrap gap-x-4">
      {email && <a href={`mailto:${email}`} className="inline-flex min-h-9 items-center gap-1.5 footnote font-medium text-accent break-all"><Mail className="size-4 shrink-0" aria-hidden />{email}</a>}
      {phone && <a href={`tel:${phone}`} className="inline-flex min-h-9 items-center gap-1.5 footnote font-medium text-accent"><Phone className="size-4" aria-hidden />{phone}</a>}
    </span>
  );
}

function PersonLines({ p }: { p: Person }) {
  const study = join([p.college, p.department, p.year]);
  return (
    <>
      {study && <p className="footnote text-text-2">{study}</p>}
      {(p.home_area || p.skill_level) && <p className="footnote text-text-2">{join([p.home_area, p.skill_level && `${p.skill_level[0].toUpperCase()}${p.skill_level.slice(1)}`])}</p>}
      {p.interests.length > 0 && <p className="footnote text-text-2">Interests: {p.interests.join(", ")}</p>}
    </>
  );
}

const Scroll = ({ children }: { children: ReactNode }) => <div className="no-scrollbar -mx-1 max-h-[68vh] overflow-y-auto overscroll-contain px-1">{children}</div>;

/** One event's registrants (or applicants), each with their details. */
export function EventPeopleSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [student, setStudent] = useState<string | null>(null);
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "event-people", id],
    queryFn: () => api<{ event: AdminEvent; registrations: Reg[]; applications: App[] }>(`/admin/events/${id}/people`),
    enabled: !!id,
  });
  const e = data?.event;
  return (
    <>
      <Sheet open={!!id && !student} onClose={onClose} title={e?.title ?? "Event"}>
        <Scroll>
          {isError ? <p className="callout text-danger-text">Couldn't load the registrations.</p>
            : isPending || !data || !e ? <div className="skeleton h-40 rounded-[14px]" /> : (
              <>
                <p className="footnote text-text-2 tnum">{join([e.organizer, formatWhen(e), e.venue_name ?? (e.mode === "online" ? "Online" : null), formatFee(e.fee_inr)])}</p>
                <p className="callout mt-1 font-medium tnum">{eventCounts(e)}</p>
                {data.registrations.length === 0 && data.applications.length === 0 ? (
                  <p className="callout mt-4 text-text-2">Nobody has registered yet.</p>
                ) : (
                  <ul className="mt-3 divide-y divide-line">
                    {[...data.applications.map((a) => ({ ...a, when: `Applied ${shortDate(a.applied_at)}`, app: a })),
                      ...data.registrations.map((r) => ({ ...r, when: join([`Registered ${shortDate(r.registered_at)}`,
                        r.waitlist_position != null && `#${r.waitlist_position} on waitlist`, r.checked_in_at && `checked in ${shortDate(r.checked_in_at)}`,
                        r.with_friends && "with friends"]), app: null }))].map((p) => {
                      const chip = REG_CHIP[p.status] ?? { text: p.status, tone: "neutral" as const };
                      return (
                        <li key={`${p.id}-${p.status}`} className="py-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <button onClick={() => setStudent(p.id)} className="headline text-left hover:text-accent">{p.name}</button>
                            <Tag tone={chip.tone}>{chip.text}</Tag>
                          </div>
                          <Contact email={p.email} />
                          <PersonLines p={p} />
                          <p className="footnote text-text-2 tnum">{p.when}</p>
                          {p.app && (
                            <div className="mt-2 rounded-[12px] bg-text/4 p-3">
                              <p className="callout whitespace-pre-wrap">{p.app.note}</p>
                              {p.app.link && <a href={p.app.link} target="_blank" rel="noopener noreferrer nofollow" className="mt-1 inline-flex min-h-9 items-center gap-1.5 footnote font-medium text-accent break-all"><ExternalLink className="size-4 shrink-0" aria-hidden />{p.app.link}</a>}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </>
            )}
        </Scroll>
      </Sheet>
      <StudentSheet id={student} onClose={() => setStudent(null)} />
    </>
  );
}

/** Every student; tap one for their details and history. */
export function StudentsAdmin() {
  const [text, setText] = useState("");
  const q = useDebounced(text);
  const [open, setOpen] = useState<string | null>(null);
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["admin", "students", q],
    queryFn: () => api<{ items: StudentRow[] }>(`/admin/students${q ? `?q=${encodeURIComponent(q)}` : ""}`).then((r) => r.items),
    placeholderData: (prev) => prev,
  });
  return (
    <section aria-label="Students">
      <SearchBox value={text} onChange={setText} placeholder="Search by name, email or college" />
      <ListState isError={isError} isPending={isPending} empty={!data?.length} refetch={refetch}>
        <p className="footnote mb-2 text-text-2 tnum">{data && count(data.length, "student")}{data?.length === 200 ? " (first 200; search to narrow)" : ""}</p>
        <ul className="card divide-y divide-line px-5">
          {data?.map((s) => (
            <Row key={s.id} onClick={() => setOpen(s.id)} title={s.name}
              lines={[s.email, join([s.college, s.department, s.year]), join([count(s.registrations, "registration"), `${s.attended} attended`, `joined ${shortDate(s.joined)}`])]} />
          ))}
        </ul>
      </ListState>
      <StudentSheet id={open} onClose={() => setOpen(null)} />
    </section>
  );
}

export function StudentSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "student", id],
    queryFn: () => api<StudentDetail>(`/admin/students/${id}`),
    enabled: !!id,
  });
  return (
    <Sheet open={!!id} onClose={onClose} title={data?.name ?? "Student"}>
      <Scroll>
        {isError ? <p className="callout text-danger-text">Couldn't load this student.</p>
          : isPending || !data ? <div className="skeleton h-40 rounded-[14px]" /> : (
            <>
              <Contact email={data.email} />
              <PersonLines p={data} />
              <p className="footnote text-text-2">{join([data.kind, data.budget_max_inr != null ? `Budget up to ${formatFee(data.budget_max_inr)}` : "Any budget",
                data.max_distance_km != null ? `travels up to ${data.max_distance_km} km` : "travels anywhere"])}</p>
              <p className="footnote text-text-2 tnum">{join([data.joined && `Joined ${shortDate(data.joined)}`, data.last_active && `last active ${shortDate(data.last_active)}`])}</p>
              {data.following.length > 0 && <p className="footnote text-text-2">Follows: {data.following.join(", ")}</p>}
              <h3 className="headline mt-5">Events ({data.history.length})</h3>
              {data.history.length === 0 ? <p className="callout mt-1 text-text-2">No registrations yet.</p> : (
                <ul className="mt-1 divide-y divide-line">
                  {data.history.map((h) => {
                    const chip = REG_CHIP[h.status] ?? { text: h.status, tone: "neutral" as const };
                    return (
                      <li key={h.event_id} className="flex items-center justify-between gap-3 py-2.5">
                        <span className="min-w-0">
                          <Link to={`/event/${h.event_id}`} className="callout font-medium hover:text-accent">{h.title}</Link>
                          <span className="footnote block text-text-2 tnum">{join([h.organizer, shortDate(h.start_at)])}</span>
                        </span>
                        <Tag tone={chip.tone}>{chip.text}</Tag>
                      </li>
                    );
                  })}
                </ul>
              )}
              {data.applications.length > 0 && (
                <>
                  <h3 className="headline mt-5">Internship applications</h3>
                  <ul className="mt-1 divide-y divide-line">
                    {data.applications.map((a) => (
                      <li key={a.event_id} className="flex items-center justify-between gap-3 py-2.5">
                        <span className="callout font-medium">{a.title}</span>
                        <Tag tone={(REG_CHIP[a.status] ?? REG_CHIP.submitted).tone}>{(REG_CHIP[a.status] ?? REG_CHIP.submitted).text}</Tag>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
      </Scroll>
    </Sheet>
  );
}

/** One organizer: contact, profile and every event with its numbers. Tap an event for its registrants. */
export function OrganizerSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [event, setEvent] = useState<string | null>(null);
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "organizer", id],
    queryFn: () => api<OrganizerDetail>(`/admin/organizers/${id}`),
    enabled: !!id,
  });
  const links = data ? [{ href: data.website, label: "Website" }, { href: data.instagram, label: "Instagram" }, { href: data.linkedin, label: "LinkedIn" }]
    .filter((l): l is { href: string; label: string } => !!l.href) : [];
  return (
    <>
      <Sheet open={!!id && !event} onClose={onClose} title={data?.name ?? "Organizer"}>
        <Scroll>
          {isError ? <p className="callout text-danger-text">Couldn't load this organizer.</p>
            : isPending || !data ? <div className="skeleton h-40 rounded-[14px]" /> : (
              <>
                <p className="callout font-medium">{data.contact_name}</p>
                <Contact email={data.email} phone={data.phone} />
                <p className="footnote text-text-2">{join([data.college_or_company, data.city, data.org_type?.replace("_", " ")])}</p>
                {data.faculty_name && <p className="footnote text-text-2">Faculty contact: {join([data.faculty_name, data.faculty_email])}</p>}
                <p className="footnote text-text-2 tnum">{join([count(data.followers, "follower"),
                  data.attendance_rate != null && `${Math.round(data.attendance_rate * 100)}% average attendance`,
                  data.joined && `joined ${shortDate(data.joined)}`, data.last_active && `last active ${shortDate(data.last_active)}`])}</p>
                {data.bio && <p className="callout mt-2 text-text-2">{data.bio}</p>}
                <div className="flex flex-wrap gap-x-4">
                  {data.slug && <Link to={`/club/${data.slug}`} className="inline-flex min-h-9 items-center footnote font-medium text-accent">Club page</Link>}
                  {links.map((l) => <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex min-h-9 items-center footnote font-medium text-accent">{l.label}</a>)}
                </div>
                <h3 className="headline mt-4">Events ({data.events.length})</h3>
                {data.events.length === 0 ? <p className="callout mt-1 text-text-2">No events yet.</p> : (
                  <ul className="divide-y divide-line">{data.events.map((e) => <EventRow key={e.id} e={e} onOpen={setEvent} showOrg={false} />)}</ul>
                )}
              </>
            )}
        </Scroll>
      </Sheet>
      <EventPeopleSheet id={event} onClose={() => setEvent(null)} />
    </>
  );
}
