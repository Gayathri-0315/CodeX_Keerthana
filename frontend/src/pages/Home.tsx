import { CalendarDays, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { EventCard, EventCardSkeleton } from "../components/events/EventCard";
import { Button } from "../components/ui/Button";
import { CountUp } from "../components/ui/CountUp";
import { Segmented } from "../components/ui/Segmented";
import { greeting } from "../lib/format";
import { useEvents, useFeedCount, useMe } from "../lib/queries";

type Tab = "for_you" | "almost";

export default function Home() {
  const { data: me } = useMe();
  const { data: count } = useFeedCount();
  const { data: events, isPending, isError, refetch } = useEvents();
  const [tab, setTab] = useState<Tab>("for_you");

  const fits = events?.filter((e) => e.fits) ?? [];
  const almost = events?.filter((e) => e.almost) ?? [];
  const list = tab === "for_you" ? fits : almost;
  const firstName = me?.name.split(" ")[0] ?? "";

  return (
    <>
      <PageHeader title={`${greeting()}, ${firstName}`} />

      <Link to="/calendar" className="pressable liftable card mb-8 flex items-center gap-4 p-5">
        <span className="grid size-12 shrink-0 place-items-center rounded-[14px] bg-success/15 text-success-text">
          <CalendarDays className="size-6" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="title-3 block">
            <CountUp value={count?.fits ?? 0} /> {count?.fits === 1 ? "event fits" : "events fit"} your week
          </span>
          <span className="callout block text-text-2">Based on your free time, distance and budget.</span>
        </span>
        <ChevronRight className="size-5 shrink-0 text-text-2" aria-hidden />
      </Link>

      <Segmented
        label="Feed"
        value={tab}
        onChange={setTab}
        className="mb-5 w-full sm:w-auto"
        options={[
          { value: "for_you", label: `For you${events ? ` · ${fits.length}` : ""}` },
          ...(me?.show_almost !== false ? [{ value: "almost" as const, label: `Almost${events ? ` · ${almost.length}` : ""}` }] : []),
        ]}
      />

      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load events.</p>
          <p className="callout mt-1 text-text-2">Check your connection, then try again.</p>
          <Button variant="secondary" className="mt-4" onClick={() => refetch()}>Try again</Button>
        </div>
      ) : isPending ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => <EventCardSkeleton key={i} />)}
        </div>
      ) : list.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="headline">{tab === "for_you" ? "Nothing fits yet." : "No near misses this week."}</p>
          <p className="callout mt-1 text-text-2">
            {tab === "for_you" ? "Add more free hours to see more events." : "Events that only clash with your schedule show up here."}
          </p>
          {tab === "for_you" && (
            <Link to="/calendar" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent px-5 font-semibold text-white">
              Add free time
            </Link>
          )}
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2" key={tab}>
          {list.map((e, i) => (
            <li key={e.id}>
              <EventCard event={e} index={i} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
