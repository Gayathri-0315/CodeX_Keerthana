import { useSearchParams } from "react-router-dom";
import { AIResults } from "../components/events/AIResults";
import { SmartSearch } from "../components/events/SmartSearch";

export type { SearchFilters } from "../components/events/AIResults";

/** /search?q=…: what the sentence was understood as (editable chips), then real events from the Explore filters. */
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="title-1 mb-4">Search</h1>
      <SmartSearch initial={q} onSearch={(text) => setParams({ q: text })} className="mb-4" />
      {q ? (
        <AIResults key={q} q={q} onClear={() => setParams({})} />
      ) : (
        <p className="callout py-6 text-text-2">Describe what you're looking for, like "free hackathons this weekend" or "AI workshop under ₹200".</p>
      )}
    </div>
  );
}
