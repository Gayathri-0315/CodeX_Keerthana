import { AnimatePresence, m } from "motion/react";
import { ArrowDown, CalendarDays, ChevronRight, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { EventCard, EventCardSkeleton } from "../components/events/EventCard";
import { Button } from "../components/ui/Button";
import { CountUp } from "../components/ui/CountUp";
import { Segmented } from "../components/ui/Segmented";
import { useToast } from "../components/ui/Toaster";
import { greeting } from "../lib/format";
import { spring } from "../lib/motion";
import { useDismissEvent, useFeed, useFeedCount, useMe, useSaveEvent, useUpdateInterests } from "../lib/queries";
import type { FeedItem, FeedTab } from "../lib/types";
import { usePullToRefresh } from "../lib/usePullToRefresh";

const EMPTY: Record<FeedTab, { title: string; body: string }> = {
  for_you: { title: "Nothing fits yet.", body: "Add more free hours to see more events." },
  almost: { title: "No near misses.", body: "Events you'd like that clash with your schedule show up here." },
  saved: { title: "Nothing saved yet.", body: "Tap the bookmark on any event to keep it here." },
};

export default function Home() {
  const { data: me } = useMe();
  const { data: count } = useFeedCount();
  const [tab, setTab] = useState<FeedTab>("for_you");
  const feed = useFeed(tab);
  const save = useSaveEvent();
  const dismiss = useDismissEvent();
  const interests = useUpdateInterests();
  const toast = useToast();
  const { pull, refreshing, ready } = usePullToRefresh(() => feed.refetch());

  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];
  const firstName = me?.name.split(" ")[0] ?? "";

  const toggleSave = (e: FeedItem) =>
    save.mutate(
      { id: e.id, saved: !e.saved },
      { onError: () => toast({ tone: "error", title: "Couldn't save", body: "Check your connection and try again." }) },
    );

  const notForMe = (e: FeedItem) =>
    dismiss.mutate(
      { id: e.id },
      {
        onSuccess: () =>
          toast({ title: "Hidden", body: "We'll show fewer like this.", action: { label: "Undo", onClick: () => dismiss.mutate({ id: e.id, undo: true }) } }),
        onError: () => toast({ tone: "error", title: "Couldn't hide that event", body: "Check your connection and try again." }),
      },
    );

  const remindSimilar = (e: FeedItem) => {
    if (!me) return;
    const weights = new Map(me.interests.map((i) => [i.tag, i.weight]));
    for (const t of e.tags) weights.set(t, Math.min(3, (weights.get(t) ?? 1) + 1));
    interests.mutate(
      { interests: [...weights].map(([tag, weight]) => ({ tag, weight })) },
      { onSuccess: () => toast({ tone: "success", title: "Got it", body: "We'll look for more events like this." }) },
    );
  };

  const tabs: { value: FeedTab; label: string }[] = [
    { value: "for_you", label: "For you" },
    ...(me?.show_almost !== false ? [{ value: "almost" as const, label: `Almost${count ? ` · ${count.almost}` : ""}` }] : []),
    { value: "saved", label: "Saved" },
  ];

  return (
    <>
      {/* Pull-to-refresh indicator; transform only, no layout shift. */}
      <div className="pointer-events-none fixed inset-x-0 top-2 z-30 flex justify-center md:hidden" aria-hidden={!refreshing}>
        <m.div
          className="glass grid size-10 place-items-center rounded-full shadow-card ring-1 ring-line"
          animate={{ y: refreshing ? 24 : pull - 50, opacity: refreshing || pull > 10 ? 1 : 0, rotate: ready ? 180 : 0 }}
          transition={spring}
        >
          {refreshing ? <Loader2 className="size-5 animate-spin text-accent" /> : <ArrowDown className="size-5 text-accent" />}
        </m.div>
      </div>

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

      <Segmented label="Feed" value={tab} onChange={setTab} className="mb-5 w-full sm:w-auto" options={tabs} />

      {feed.isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load events.</p>
          <p className="callout mt-1 text-text-2">Check your connection, then try again.</p>
          <Button variant="secondary" className="mt-4" onClick={() => feed.refetch()}>Try again</Button>
        </div>
      ) : feed.isPending ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => <EventCardSkeleton key={i} />)}
        </div>
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="headline">{EMPTY[tab].title}</p>
          <p className="callout mt-1 text-text-2">{EMPTY[tab].body}</p>
          {tab === "for_you" && (
            <Link to="/calendar" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent px-5 font-semibold text-white">
              Add free time
            </Link>
          )}
        </div>
      ) : (
        <>
          <ul className="grid gap-3 md:grid-cols-2" key={tab}>
            <AnimatePresence initial={false} mode="popLayout">
              {items.map((e, i) => (
                <m.li key={e.id} layout="position" exit={{ opacity: 0, scale: 0.96 }} transition={spring}>
                  <EventCard
                    event={e}
                    index={i}
                    onToggleSave={toggleSave}
                    onDismiss={tab === "saved" ? undefined : notForMe}
                    onRemindSimilar={tab === "almost" ? remindSimilar : undefined}
                  />
                </m.li>
              ))}
            </AnimatePresence>
          </ul>
          {feed.hasNextPage && (
            <div className="mt-6 flex justify-center">
              <Button variant="secondary" loading={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()}>Show more</Button>
            </div>
          )}
          {tab !== "saved" && <p className="footnote mt-6 text-center text-text-2">Swipe a card left if it's not for you.</p>}
        </>
      )}
    </>
  );
}
