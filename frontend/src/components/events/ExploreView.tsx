import { ArrowRight, Loader2, Search, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCategories, useExplore, type ExploreFilters } from "../../lib/queries";
import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { Sheet } from "../ui/Sheet";
import { Timeline } from "./Timeline";

const inputCls =
  "h-12 w-full rounded-[14px] bg-surface px-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]";

/**
 * Every upcoming event, by start date, with search, filters and infinite scroll.
 * Students (source "feed") get time-fit badges and saves; guests and organizers browse public cards.
 */
export function ExploreView({ source = "feed", category, eventType }: {
  source?: "feed" | "public";
  /** From the opportunity tabs. */
  eventType?: string;
  /** Fixed category (category pages): hides the category filter. */
  category?: string;
}) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [filters, setFilters] = useState<ExploreFilters>({});
  const [sheet, setSheet] = useState(false);
  const feed = useExplore({ ...filters, ...(category ? { category } : {}), ...(eventType ? { event_type: eventType } : {}) }, source);
  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];
  const active = [filters.category, filters.date_from || filters.date_to, filters.price, filters.mode].filter(Boolean).length;

  // A word or two filters this list as you type; a sentence ("free AI workshops this weekend") goes to the AI search.
  const sentence = text.trim().split(/\s+/).filter(Boolean).length >= 3;
  const askAI = () => text.trim() && navigate(`/search?q=${encodeURIComponent(text.trim())}`);

  // Search shortly after typing stops.
  useEffect(() => {
    const q = (text.trim().split(/\s+/).filter(Boolean).length >= 3 ? "" : text.trim().slice(0, 100)) || undefined;
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
      <div className="mb-3 flex gap-2">
        <form role="search" className="relative flex-1" onSubmit={(e) => {
          e.preventDefault();
          askAI();
        }}>
          <label>
          <span className="sr-only">Search events, or describe what you want and press Enter</span>
          <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
          <input type="search" enterKeyHint="search" value={text} onChange={(e) => setText(e.target.value)} placeholder='Search, or ask "free hackathons this weekend"' maxLength={200} className={`${inputCls} pl-11`} />
          </label>
        </form>
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

      {sentence && (
        <button onClick={askAI} className="pressable mb-3 flex w-full items-center gap-3 rounded-[14px] bg-accent-soft p-3.5 text-left">
          <Sparkles className="size-5 shrink-0 text-accent" aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="callout block font-medium text-text">Ask ShowUp AI</span>
            <span className="footnote block truncate text-text-2">"{text.trim()}" · press Enter</span>
          </span>
          <ArrowRight className="size-5 shrink-0 text-accent" aria-hidden />
        </button>
      )}

      <div className="no-scrollbar -mx-4 mb-6 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:px-0" role="group" aria-label="Quick filters">
        {source === "feed" && (
          <QuickChip on={filters.following === "true"} label="Following" onClick={() => setFilters((f) => ({ ...f, following: f.following ? undefined : "true" }))} />
        )}
        <QuickChip on={filters.price === "free"} label="Free" onClick={() => setFilters((f) => ({ ...f, price: f.price === "free" ? undefined : "free" }))} />
        <QuickChip on={filters.price === "paid"} label="Paid" onClick={() => setFilters((f) => ({ ...f, price: f.price === "paid" ? undefined : "paid" }))} />
        <QuickChip on={filters.mode === "in_person"} label="In person" onClick={() => setFilters((f) => ({ ...f, mode: f.mode === "in_person" ? undefined : "in_person" }))} />
        <QuickChip on={filters.mode === "online"} label="Online" onClick={() => setFilters((f) => ({ ...f, mode: f.mode === "online" ? undefined : "online" }))} />
        <QuickChip on={!!(filters.date_from || filters.date_to)} label={filters.date_from || filters.date_to ? "Dates set" : "Dates"} onClick={() => setSheet(true)} />
      </div>

      {feed.isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load events.</p>
          <p className="callout mt-1 text-text-2">Check your connection, then try again.</p>
          <Button variant="secondary" className="mt-4" onClick={() => feed.refetch()}>Try again</Button>
        </div>
      ) : feed.isPending ? (
        <TimelineSkeleton />
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="headline">No events match.</p>
          <p className="callout mt-1 text-text-2">Try another search or clear the filters.</p>
          {(active > 0 || filters.q) && <Button variant="secondary" className="mt-4" onClick={clearAll}>Clear filters</Button>}
        </div>
      ) : (
        <>
          <div className={`transition-opacity ${feed.isPlaceholderData ? "opacity-60" : ""}`}>
            <Timeline items={items} />
          </div>
          <div ref={sentinel} className="flex h-16 items-center justify-center">
            {feed.isFetchingNextPage && <Loader2 className="size-5 animate-spin text-text-2" aria-label="Loading more events" />}
          </div>
        </>
      )}

      <FilterSheet
        showCategory={!category}
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

function FilterSheet({ open, onClose, value, onApply, showCategory }: {
  showCategory: boolean;
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
        {showCategory && (
          <div>
            <label htmlFor="f-category" className="footnote mb-1.5 block font-medium text-text-2">Category</label>
            <select id="f-category" value={draft.category ?? ""} onChange={(e) => set({ category: e.target.value || undefined })} className={inputCls}>
              <option value="">All categories</option>
              {categories?.map((c) => <option key={c.slug} value={c.slug}>{c.emoji} {c.name}</option>)}
            </select>
          </div>
        )}
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

function QuickChip({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={`pressable min-h-9 shrink-0 rounded-full px-3.5 callout font-medium transition-colors ${on ? "bg-accent-fill text-white" : "bg-surface text-text shadow-[inset_0_0_0_1px_var(--line)]"}`}
    >
      {label}
    </button>
  );
}

function TimelineSkeleton() {
  return (
    <div className="flex flex-col gap-6 pl-5" aria-hidden>
      {[0, 1].map((g) => (
        <div key={g}>
          <div className="skeleton mb-3 h-4 w-28 rounded-full" />
          {[0, 1].map((r) => (
            <div key={r} className="flex gap-4 py-3">
              <div className="flex-1 space-y-2">
                <div className="skeleton h-3 w-20 rounded-full" />
                <div className="skeleton h-4 w-3/4 rounded-full" />
                <div className="skeleton h-3 w-1/2 rounded-full" />
              </div>
              <div className="skeleton size-[76px] rounded-[16px]" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
