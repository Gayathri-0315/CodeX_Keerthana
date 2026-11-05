import { AnimatePresence, m } from "motion/react";
import { ArrowDown, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { EventCard, EventCardSkeleton } from "../components/events/EventCard";
import { ExploreView } from "../components/events/ExploreView";
import { YourWeek } from "../components/week/YourWeek";
import { OpportunityTabs, typeParam, type TypeTab } from "../components/events/OpportunityTabs";
import { Button } from "../components/ui/Button";
import { Segmented } from "../components/ui/Segmented";
import { useToast } from "../components/ui/Toaster";
import { greeting } from "../lib/format";
import { spring } from "../lib/motion";
import { useCreateAlert, useDismissEvent, useFeed, useFeedCount, useMe, useSaveEvent } from "../lib/queries";
import type { FeedItem, FeedTab, HomeTab } from "../lib/types";
import { usePullToRefresh } from "../lib/usePullToRefresh";

const EMPTY: Record<FeedTab, { title: string; body: string }> = {
  for_you: { title: "Nothing fits yet.", body: "Add more free hours to see more events." },
  almost: { title: "No near misses.", body: "Events you'd like that clash with your schedule show up here." },
  saved: { title: "Nothing saved yet.", body: "Tap the bookmark on any event to keep it here." },
};

export default function Home() {
  const { data: me } = useMe();
  const { data: count } = useFeedCount();
  const [tab, setTab] = useState<HomeTab>("for_you");
  const [type, setType] = useState<TypeTab>("all");
  const feedTab: FeedTab = tab === "explore" ? "for_you" : tab;
  const feed = useFeed(feedTab, typeParam(type));
  const save = useSaveEvent();
  const dismiss = useDismissEvent();
  const createAlert = useCreateAlert();
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

  const remindSimilar = (e: FeedItem) =>
    createAlert.mutate(e.id, {
      onSuccess: () => toast({ tone: "success", title: "Got it. We'll tell you about similar events." }),
      onError: (err) => toast({ tone: "error", title: "Couldn't save the alert", body: (err as Error).message }),
    });

  const tabs: { value: HomeTab; label: string }[] = [
    { value: "for_you", label: "For you" },
    { value: "explore", label: "Explore" },
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

      <YourWeek className="mb-6" />

      <OpportunityTabs value={type} onChange={setType} className="mb-4" />
      <Segmented label="Feed" value={tab} onChange={setTab} className="mb-5 w-full sm:w-auto" options={tabs} />

      {tab === "explore" ? (
        <ExploreView eventType={typeParam(type)} />
      ) : feed.isError ? (
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
          <p className="headline">{EMPTY[feedTab].title}</p>
          <p className="callout mt-1 text-text-2">{EMPTY[feedTab].body}</p>
          {tab === "for_you" && (
            <Link to="/calendar" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">
              Add free time
            </Link>
          )}
        </div>
      ) : (
        <>
          <ul className="grid gap-3 md:grid-cols-2" key={`${tab}-${type}`}>
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
