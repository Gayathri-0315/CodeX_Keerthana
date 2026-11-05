import { useQuery } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { formatDayTime, formatLongDate } from "../../lib/format";
import { useCategories } from "../../lib/queries";
import { CountUp } from "../ui/CountUp";
import { RecapCard } from "./RecapCard";

export type RecordData = {
  events_attended: number;
  hours: number;
  current_streak_weeks: number;
  longest_streak_weeks: number;
  events: { event_id: string; title: string; start_at: string; end_at: string; organizer_name: string | null; category_slug: string | null; event_type: string }[];
};

export function useRecord() {
  return useQuery({ queryKey: ["registrations", "me", "record"], queryFn: () => api<RecordData>("/me/record"), staleTime: 60_000 });
}

/** Private participation record: only organizer-confirmed check-ins. `top` is where the recap card goes. */
export function RecordView() {
  const { data, isPending, isError, refetch } = useRecord();
  const { data: categories } = useCategories();
  if (isError) {
    return (
      <div className="card p-6 text-center">
        <p className="headline">Couldn't load your record.</p>
        <button onClick={() => refetch()} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
      </div>
    );
  }
  if (isPending) return <div className="skeleton h-40 rounded-[22px]" aria-busy="true" />;
  if (data.events_attended === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="headline">Your record starts at your first event.</p>
        <p className="callout mt-1 text-text-2">When an organizer checks you in, the event appears here. It's private to you.</p>
        <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Find an event</Link>
      </div>
    );
  }

  const catName = (slug: string | null) => categories?.find((c) => c.slug === slug)?.name;
  const months: { label: string; items: RecordData["events"] }[] = [];
  for (const e of data.events) {
    const label = new Date(e.start_at).toLocaleDateString("en-IN", { month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
    const last = months[months.length - 1];
    if (last?.label === label) last.items.push(e);
    else months.push({ label, items: [e] });
  }

  return (
    <div>
      <RecapCard />
      <dl className="mb-2 grid grid-cols-3 gap-3">
        <Stat label="Events attended" value={<CountUp value={data.events_attended} />} />
        <Stat label="Hours learning" value={<CountUp value={Math.round(data.hours)} />} />
        <Stat label="Week streak" value={<CountUp value={data.current_streak_weeks} />} />
      </dl>
      <p className="footnote mb-6 px-1 text-text-2">Private to you. Only events where an organizer checked you in count.</p>
      <div className="flex flex-col gap-6">
        {months.map((m) => (
          <section key={m.label} aria-label={m.label}>
            <h2 className="footnote mb-2 px-1 font-semibold uppercase tracking-wide text-text-2">{m.label}</h2>
            <ul className="card divide-y divide-line px-5">
              {m.items.map((e) => (
                <li key={e.event_id}>
                  <Link to={`/event/${e.event_id}`} className="pressable -mx-2 flex min-h-16 flex-col justify-center rounded-[12px] px-2 py-3 hover:bg-text/3">
                    <span className="footnote text-text-2 tnum">{formatLongDate(e.start_at)} · {formatDayTime(e.start_at, e.end_at).split(", ")[1]}</span>
                    <span className="headline">{e.title}</span>
                    <span className="callout text-text-2">{[e.organizer_name, catName(e.category_slug)].filter(Boolean).join(" · ")}</span>
                    <span className="footnote mt-1 inline-flex items-center gap-1 text-success-text">
                      <BadgeCheck className="size-3.5" aria-hidden /> Confirmed by organizer check-in
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="card px-3 py-4 text-center">
      <dd className="title-2 tnum">{value}</dd>
      <dt className="footnote mt-0.5 text-text-2">{label}</dt>
    </div>
  );
}
