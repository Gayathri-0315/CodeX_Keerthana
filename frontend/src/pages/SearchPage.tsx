import { useMutation, useQuery } from "@tanstack/react-query";
import { MapPinOff, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ClubResults } from "../components/events/ClubResults";
import { SmartSearch } from "../components/events/SmartSearch";
import { Timeline } from "../components/events/Timeline";
import { Button } from "../components/ui/Button";
import { api } from "../lib/api";
import type { FeedItem } from "../lib/types";

export type SearchFilters = {
  categories: string[];
  tags: string[];
  event_type: string | null;
  when: string | null;
  date_from: string | null;
  date_to: string | null;
  time_of_day: string | null;
  max_fee_inr: number | null;
  free_only: boolean;
  mode: string | null;
  max_distance_km: number | null;
  near: string | null;
  near_lat: number | null;
  near_lng: number | null;
  keywords: string[];
};
type Chip = { field: keyof SearchFilters; value: string | number | boolean | null; label: string };
type Parsed = { filters: SearchFilters; chips: Chip[]; source: "ai" | "rules"; note: string | null };
type Results = { items: FeedItem[]; total: number; relaxed: { message: string; filters: SearchFilters; chips: Chip[] } | null };

/** Remove one chip: lists drop that value, everything else goes back to "any". */
function without(f: SearchFilters, chip: Chip): SearchFilters {
  const v = f[chip.field];
  if (Array.isArray(v)) return { ...f, [chip.field]: v.filter((x) => x !== chip.value) };
  if (chip.field === "when") return { ...f, when: null, date_from: null, date_to: null };
  if (chip.field === "near") return { ...f, near: null, near_lat: null, near_lng: null, max_distance_km: null };
  return { ...f, [chip.field]: chip.field === "free_only" ? false : null };
}

const chipsFor = (f: SearchFilters, all: Chip[]) =>
  all.filter((c) => {
    const v = f[c.field];
    if (Array.isArray(v)) return v.includes(c.value as never);
    if (c.field === "when") return !!(f.when || f.date_from || f.date_to);
    return v === c.value;
  });

/** /search?q=…: what the sentence was understood as (editable chips), then real events from the Explore filters. */
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [filters, setFilters] = useState<SearchFilters | null>(null);
  const [allChips, setAllChips] = useState<Chip[]>([]);
  const [note, setNote] = useState<string | null>(null);

  const parse = useMutation({
    mutationFn: (text: string) => api<Parsed>("/search/parse", { method: "POST", body: { text } }),
    onSuccess: (p) => {
      setFilters(p.filters);
      setAllChips(p.chips);
      setNote(p.note);
    },
  });
  useEffect(() => {
    if (q) parse.mutate(q);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const results = useQuery({
    queryKey: ["search", filters],
    queryFn: () => api<Results>("/search/results", { method: "POST", body: { filters, limit: 50 } }),
    enabled: !!filters,
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });

  const chips = filters ? chipsFor(filters, allChips) : [];
  const clear = () => {
    setFilters(null);
    setAllChips([]);
    setNote(null);
    setParams({});
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="title-1 mb-4">Search</h1>
      <SmartSearch initial={q} onSearch={(text) => (text === q ? parse.mutate(text) : setParams({ q: text }))} className="mb-4" />

      {parse.isPending ? (
        <p className="callout flex items-center gap-2 py-4 text-text-2" role="status">
          <Sparkles className="size-4 animate-pulse text-accent" aria-hidden /> Understanding your search...
        </p>
      ) : parse.isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Search didn't work.</p>
          <p className="callout mt-1 text-text-2">{(parse.error as Error).message}</p>
          <Button variant="secondary" className="mt-4" onClick={() => parse.mutate(q)}>Try again</Button>
        </div>
      ) : !filters ? (
        <p className="callout py-6 text-text-2">Describe what you're looking for, like "free hackathons this weekend" or "AI workshop under ₹200".</p>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2" role="group" aria-label="What we understood">
            {chips.length === 0 ? (
              <span className="callout text-text-2">Showing every upcoming event.</span>
            ) : (
              chips.map((c) => (
                <button key={`${c.field}-${String(c.value)}`} onClick={() => setFilters(without(filters, c))}
                  aria-label={`Remove ${c.label}`}
                  className="pressable inline-flex min-h-9 items-center gap-1 rounded-full bg-accent-soft py-1 pl-3.5 pr-2.5 callout font-medium text-accent">
                  {c.label} <X className="size-4" aria-hidden />
                </button>
              ))
            )}
            {(chips.length > 0 || q) && <Button size="sm" variant="quiet" onClick={clear}>Clear</Button>}
          </div>

          {note && <p className="callout -mt-2 mb-5 flex items-start gap-2 text-text-2" role="status"><MapPinOff className="mt-0.5 size-4 shrink-0" aria-hidden />{note}</p>}

          <ClubResults q={q} />

          {results.isError ? (
            <div className="card p-6 text-center">
              <p className="headline">Couldn't load events.</p>
              <Button variant="secondary" className="mt-4" onClick={() => results.refetch()}>Try again</Button>
            </div>
          ) : !results.data ? (
            <div className="flex flex-col gap-3" aria-busy="true">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-24 rounded-[22px]" />)}</div>
          ) : results.data.items.length === 0 ? (
            <div className="card p-8 text-center">
              <p className="headline">No events match.</p>
              <p className="callout mt-1 text-text-2">Remove a chip above or try different words.</p>
            </div>
          ) : (
            <div className={`transition-opacity ${results.isPlaceholderData ? "opacity-60" : ""}`}>
              {results.data.relaxed && (
                <div className="mb-5 rounded-[14px] bg-warning/12 p-4">
                  <p className="callout text-warning-text">{results.data.relaxed.message}</p>
                  <Button size="sm" variant="quiet" className="-ml-3.5 mt-1" onClick={() => {
                    setFilters(results.data!.relaxed!.filters);
                    setAllChips(results.data!.relaxed!.chips);
                  }}>Use these filters</Button>
                </div>
              )}
              <p className="footnote mb-3 text-text-2 tnum">{results.data.total === 1 ? "1 event" : `${results.data.total} events`}</p>
              <Timeline items={results.data.items} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
