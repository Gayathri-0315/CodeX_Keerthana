import { AnimatePresence, m } from "motion/react";
import { Loader2, Search, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { spring } from "../../lib/motion";
import { useCategories, useExplore, type ExploreFilters } from "../../lib/queries";
import type { FeedItem } from "../../lib/types";
import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { Sheet } from "../ui/Sheet";
import { EventCard, EventCardSkeleton } from "./EventCard";

const inputCls =
  "h-12 w-full rounded-[14px] bg-surface px-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]";

/** Every upcoming event, by start date, with search, filters and infinite scroll. */
export function ExploreView({ onToggleSave }: { onToggleSave: (e: FeedItem) => void }) {
  const [text, setText] = useState("");
  const [filters, setFilters] = useState<ExploreFilters>({});
  const [sheet, setSheet] = useState(false);
  const feed = useExplore(filters);
  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];
  const active = [filters.category, filters.date_from || filters.date_to, filters.price, filters.mode].filter(Boolean).length;

  // Search shortly after typing stops.
  useEffect(() => {
    const q = text.trim() || undefined;
    const t = window.setTimeout(() => setFilters((f) => (f.q === q ? f : { ...f, q })), 300);
    return () => window.clearTimeout(t);
  }, [text]);

  // Infinite scroll: load the next page when the sentinel comes near the viewport.
  const sentinel = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = feed;
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) void fetchNextPage();
      },
      { rootMargin: "400px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, items.length]);

  const clearAll = () => {
    setText("");
    setFilters({});
  };

  return (
    <>
      <div className="mb-5 flex gap-2">
        <label className="relative flex-1">
          <span className="sr-only">Search events by title</span>
          <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
          <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search events" maxLength={100} className={`${inputCls} pl-11`} />
        </label>
        <button
          onClick={() => setSheet(true)}
          aria-label={active ? `Filters, ${active} on` : "Filters"}
          className={`pressable relative grid size-12 shrink-0 place-items-center rounded-[14px] ${active ? "bg-accent-soft text-accent" : "bg-surface text-text shadow-[inset_0_0_0_1px_var(--line)]"}`}
        >
          <SlidersHorizontal className="size-5" aria-hidden />
          {active > 0 && (
            <span className="absolute -right-1 -top-1 grid size-5 place-items-center rounded-full bg-accent-fill text-[11px] font-semibold text-white tnum">{active}</span>
          )}
        </button>
      </div>

      {feed.isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load events.</p>
          <p className="callout mt-1 text-text-2">Check your connection, then try again.</p>
          <Button variant="secondary" className="mt-4" onClick={() => feed.refetch()}>Try again</Button>
        </div>
      ) : feed.isPending ? (
        <div className="grid gap-3 md:grid-cols-2">{Array.from({ length: 4 }, (_, i) => <EventCardSkeleton key={i} />)}</div>
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="headline">No events match.</p>
          <p className="callout mt-1 text-text-2">Try another search or clear the filters.</p>
          {(active > 0 || filters.q) && <Button variant="secondary" className="mt-4" onClick={clearAll}>Clear filters</Button>}
        </div>
      ) : (
        <>
          <ul className={`grid gap-3 transition-opacity md:grid-cols-2 ${feed.isPlaceholderData ? "opacity-60" : ""}`}>
            <AnimatePresence initial={false} mode="popLayout">
              {items.map((e, i) => (
                <m.li key={e.id} layout="position" exit={{ opacity: 0, scale: 0.96 }} transition={spring}>
                  <EventCard event={e} index={i} onToggleSave={onToggleSave} variant="explore" />
                </m.li>
              ))}
            </AnimatePresence>
          </ul>
          <div ref={sentinel} className="flex h-16 items-center justify-center">
            {feed.isFetchingNextPage && <Loader2 className="size-5 animate-spin text-text-2" aria-label="Loading more events" />}
          </div>
        </>
      )}

      <FilterSheet
        open={sheet}
        onClose={() => setSheet(false)}
        value={filters}
        onApply={(f) => {
          setFilters({ ...f, q: filters.q });
          setSheet(false);
        }}
      />
    </>
  );
}

function FilterSheet({ open, onClose, value, onApply }: {
  open: boolean;
  onClose: () => void;
  value: ExploreFilters;
  onApply: (f: ExploreFilters) => void;
}) {
  const { data: categories } = useCategories();
  const [draft, setDraft] = useState(value);
  useEffect(() => {
    if (open) setDraft(value);
  }, [open, value]);
  const set = (p: Partial<ExploreFilters>) => setDraft((d) => ({ ...d, ...p }));

  return (
    <Sheet open={open} onClose={onClose} title="Filters">
      <div className="flex flex-col gap-5">
        <div>
          <label htmlFor="f-category" className="footnote mb-1.5 block font-medium text-text-2">Category</label>
          <select id="f-category" value={draft.category ?? ""} onChange={(e) => set({ category: e.target.value || undefined })} className={inputCls}>
            <option value="">All categories</option>
            {categories?.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="f-from" className="footnote mb-1.5 block font-medium text-text-2">From</label>
            <input id="f-from" type="date" value={draft.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value || undefined })} className={inputCls} />
          </div>
          <div>
            <label htmlFor="f-to" className="footnote mb-1.5 block font-medium text-text-2">To</label>
            <input id="f-to" type="date" min={draft.date_from} value={draft.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value || undefined })} className={inputCls} />
          </div>
        </div>
        <div>
          <p className="footnote mb-1.5 font-medium text-text-2">Price</p>
          <Segmented label="Price" className="w-full" value={draft.price ?? "any"} onChange={(v) => set({ price: v === "any" ? undefined : v })}
            options={[{ value: "any", label: "Any" }, { value: "free", label: "Free" }, { value: "paid", label: "Paid" }]} />
        </div>
        <div>
          <p className="footnote mb-1.5 font-medium text-text-2">Format</p>
          <Segmented label="Format" className="w-full" value={draft.mode ?? "any"} onChange={(v) => set({ mode: v === "any" ? undefined : v })}
            options={[{ value: "any", label: "Any" }, { value: "in_person", label: "In person" }, { value: "online", label: "Online" }]} />
        </div>
        <div className="mt-1 flex flex-col gap-2">
          <Button size="lg" full onClick={() => onApply(draft)}>Show events</Button>
          <Button variant="quiet" full onClick={() => onApply({})}><X className="size-4" aria-hidden />Clear filters</Button>
        </div>
      </div>
    </Sheet>
  );
}
