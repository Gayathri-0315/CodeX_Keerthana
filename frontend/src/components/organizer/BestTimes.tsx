import { useMutation } from "@tanstack/react-query";
import { CalendarClock, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { EventForm } from "../../lib/types";
import { Button } from "../ui/Button";

type Option = { start_at: string; end_at: string; label: string; count: number };
type Result = { ready: boolean; current: number; pool: number; options: Option[] };

const ist = (iso: string) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(new Date(iso)).reduce<Record<string, string>>((o, p) => ({ ...o, [p.type]: p.value }), {});

/** "Find a better time": start times in the next days that reach more students who fit and are free. */
export function BestTimes({ form, onChange }: { form: EventForm; onChange: (patch: Partial<EventForm>, field: string) => void }) {
  const [used, setUsed] = useState<string | null>(null);
  const find = useMutation({ mutationFn: () => api<Result>("/organizer/events/best-times", { method: "POST", body: form }) });
  // A changed draft makes old suggestions stale.
  useEffect(() => {
    if (!used) find.reset();
  }, [form.title, form.tags.join(), form.category_slug, form.mode, form.fee_inr, form.eligibility_tags.join()]); // eslint-disable-line react-hooks/exhaustive-deps

  if (form.event_type === "internship" || !form.date || !form.start_time || !form.end_time) return null;
  const r = find.data;

  const apply = (o: Option) => {
    const s = ist(o.start_at), e = ist(o.end_at);
    onChange({ date: `${s.year}-${s.month}-${s.day}`, start_time: `${s.hour}:${s.minute}`, end_time: `${e.hour}:${e.minute}` }, "date");
    setUsed(o.start_at);
  };

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2">
        <CalendarClock className="size-5 text-accent" aria-hidden />
        <p className="headline">Best time to schedule</p>
      </div>
      {!r ? (
        <>
          <p className="callout mt-1 text-text-2">See if another day or time would reach more students who'd like this event and are actually free.</p>
          <Button size="sm" variant="secondary" className="mt-3" loading={find.isPending} onClick={() => { setUsed(null); find.mutate(); }}>Find a better time</Button>
          {find.isError && <p className="callout mt-2 text-danger-text">{(find.error as Error).message}</p>}
        </>
      ) : !r.ready ? (
        <p className="callout mt-1 text-text-2">Add a date and time first.</p>
      ) : r.options.length === 0 ? (
        <p className="callout mt-1 text-text-2">
          {r.pool === 0 ? "Not enough matching students yet to compare times." : `Your time already works well: about ${r.current} ${r.current === 1 ? "student who'd like it is" : "students who'd like it are"} free then. Nothing in the next 10 days clearly beats it.`}
        </p>
      ) : (
        <>
          <p className="callout mt-1 text-text-2">At your time, about <span className="font-semibold text-text tnum">{r.current}</span> {r.current === 1 ? "student who'd like it is" : "students who'd like it are"} free. These reach more:</p>
          <ul className="mt-3 flex flex-col gap-2">
            {r.options.map((o) => (
              <li key={o.start_at} className="flex items-center justify-between gap-3 rounded-[14px] bg-text/4 px-3.5 py-2.5">
                <div className="min-w-0">
                  <p className="callout font-medium">{o.label}</p>
                  <p className="footnote text-text-2 tnum">About {o.count} free and interested{r.current ? ` (${Math.round(o.count / Math.max(r.current, 1) * 10) / 10}×)` : ""}</p>
                </div>
                <Button size="sm" variant={used === o.start_at ? "quiet" : "secondary"} disabled={used === o.start_at} onClick={() => apply(o)} className="shrink-0">
                  {used === o.start_at ? <><Check className="size-4" aria-hidden /> Using</> : "Use"}
                </Button>
              </li>
            ))}
          </ul>
          <p className="footnote mt-2 text-text-2">From students' free time and interests on ShowUp. Counts only, never who.</p>
        </>
      )}
    </div>
  );
}
