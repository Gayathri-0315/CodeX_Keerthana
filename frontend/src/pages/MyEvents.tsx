import { Clock, MapPin, ThumbsDown, ThumbsUp, Ticket } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { PassSheet } from "../components/attendance/PassSheet";
import { RecordView } from "../components/record/RecordView";
import { Thumb } from "../components/events/EventCard";
import { Button } from "../components/ui/Button";
import { Tag } from "../components/ui/Chip";
import { Segmented } from "../components/ui/Segmented";
import { useToast } from "../components/ui/Toaster";
import { countdown, mmss, useConfirmSeat, useFeedback, useMyRegistrations } from "../lib/attendance";
import { formatDayTime, formatTime } from "../lib/format";
import type { Registration } from "../lib/types";
import { useNow } from "../lib/useNow";

type Tab = "upcoming" | "waitlist" | "past" | "record";

export default function MyEvents() {
  const { data, isPending, isError, refetch } = useMyRegistrations();
  const [tab, setTab] = useState<Tab>("upcoming");
  const [pass, setPass] = useState<Registration | null>(null);
  const now = useNow(1000);
  const list = tab === "record" ? [] : data?.[tab] ?? [];

  return (
    <>
      <PageHeader title="My events" />
      <Segmented
        label="My events"
        className="mb-5 w-full sm:w-auto"
        value={tab}
        onChange={setTab}
        options={[
          { value: "upcoming", label: `Upcoming${data ? ` · ${data.upcoming.length}` : ""}` },
          { value: "waitlist", label: `Waitlist${data?.waitlist.length ? ` · ${data.waitlist.length}` : ""}` },
          { value: "past", label: "Past" },
          { value: "record", label: "Record" },
        ]}
      />
      {tab === "record" ? (
        <RecordView />
      ) : isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load your events.</p>
          <Button variant="secondary" className="mt-4" onClick={() => refetch()}>Try again</Button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-32 rounded-[22px]" />
      ) : list.length === 0 ? (
        <Empty tab={tab as Exclude<Tab, "record">} />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {list.map((r) => (
            <li key={r.id}>
              {tab === "past" ? <PastCard reg={r} /> : <PassCard reg={r} now={now} onOpen={() => setPass(r)} />}
            </li>
          ))}
        </ul>
      )}
      <PassSheet reg={pass} open={!!pass} onClose={() => setPass(null)} />
    </>
  );
}

function Empty({ tab }: { tab: Exclude<Tab, "record"> }) {
  const copy = {
    upcoming: ["No events yet.", "Events you register for show up here with your pass."],
    waitlist: ["You're not on any waitlists.", "When an event is full, join its waitlist and we'll tell you if a seat opens."],
    past: ["Nothing here yet.", "Events you've been to show up here."],
  }[tab];
  return (
    <div className="card p-8 text-center">
      <Ticket className="mx-auto size-10 text-text-2" aria-hidden />
      <p className="headline mt-3">{copy[0]}</p>
      <p className="callout mt-1 text-text-2">{copy[1]}</p>
      {tab !== "past" && (
        <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Find events</Link>
      )}
    </div>
  );
}

function PassCard({ reg, now, onOpen }: { reg: Registration; now: number; onOpen: () => void }) {
  const e = reg.event;
  const confirm = useConfirmSeat();
  const toast = useToast();
  const offer = reg.status === "promoted_pending" && reg.promotion_expires_at;
  return (
    <div className="card overflow-hidden">
      <button onClick={onOpen} disabled={!!offer} className="pressable flex w-full gap-4 p-4 text-left" aria-label={`Open pass for ${e.title}`}>
        <Thumb event={{ ...e, id: `my-${reg.id}` }} className="size-16 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="headline line-clamp-2">{e.title}</p>
          <p className="footnote mt-0.5 text-text-2 tnum">{formatDayTime(e.start_at, e.end_at)}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {reg.status === "waitlisted" ? (
              <Tag tone="warning">Waitlist #{reg.waitlist_position}</Tag>
            ) : (
              <Tag tone="accent"><Clock className="size-3.5" aria-hidden />{countdown(e.start_at, now)}</Tag>
            )}
            {reg.leave_by && reg.status === "registered" && <Tag><MapPin className="size-3.5" aria-hidden />Leave by {formatTime(reg.leave_by)}</Tag>}
          </div>
        </div>
      </button>
      {offer && (
        <div className="flex items-center justify-between gap-3 bg-warning/12 px-4 py-3">
          <p className="callout font-medium text-warning-text tnum">A seat is yours for {mmss(reg.promotion_expires_at!, now)}</p>
          <Button
            size="sm"
            loading={confirm.isPending}
            onClick={() =>
              confirm.mutate(reg.id, {
                onSuccess: () => toast({ tone: "success", title: "Seat confirmed", body: "It's yours. See you there." }),
                onError: (err) => toast({ tone: "error", title: "Couldn't confirm", body: (err as Error).message }),
              })
            }
          >
            Confirm seat
          </Button>
        </div>
      )}
    </div>
  );
}

function PastCard({ reg }: { reg: Registration }) {
  const fb = useFeedback();
  const e = reg.event;
  const given = reg.feedback;
  return (
    <div className="card p-4">
      <div className="flex gap-4">
        <Thumb event={{ ...e, id: `past-${reg.id}` }} className="size-14 shrink-0 opacity-80" />
        <div className="min-w-0 flex-1">
          <p className="headline line-clamp-2">{e.title}</p>
          <p className="footnote text-text-2 tnum">{formatDayTime(e.start_at, e.end_at)}</p>
          <div className="mt-1.5">
            {reg.status === "attended" ? <Tag tone="success">Attended</Tag> : reg.status === "no_show" ? <Tag>Missed</Tag> : <Tag>Ended</Tag>}
          </div>
        </div>
      </div>
      {reg.status === "attended" && (
        <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
          <p className="callout text-text-2">Was it as described?</p>
          <div className="flex gap-1" role="group" aria-label="Was it as described?">
            {(["as_described", "not_as_described"] as const).map((kind) => {
              const Icon = kind === "as_described" ? ThumbsUp : ThumbsDown;
              const on = given === kind;
              return (
                <button
                  key={kind}
                  aria-pressed={on}
                  aria-label={kind === "as_described" ? "Yes" : "No"}
                  onClick={() => fb.mutate({ id: reg.id, kind })}
                  className={`pressable grid size-11 place-items-center rounded-full ${on ? "bg-accent-fill text-white" : "bg-text/6 text-text-2"}`}
                >
                  <Icon className="size-5" />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
