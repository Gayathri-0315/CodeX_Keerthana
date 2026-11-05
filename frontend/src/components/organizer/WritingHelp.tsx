import { useMutation } from "@tanstack/react-query";
import { Check, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { api } from "../../lib/api";
import { INTERESTS } from "../../lib/constants";
import { useCategories } from "../../lib/queries";
import type { EventForm } from "../../lib/types";
import { Button } from "../ui/Button";

type Suggestion = {
  description: string;
  title: string | null;
  event_type: EventForm["event_type"] | null;
  category: string | null;
  tags: string[];
  source: "ai" | "rules";
};

/** "Help me write": suggestions the organizer applies one by one. Nothing changes until they tap Use. */
export function WritingHelp({ form, onApply, typeLabel }: {
  form: EventForm;
  onApply: (patch: Partial<EventForm>, field: keyof EventForm) => void;
  typeLabel: (t: EventForm["event_type"]) => string;
}) {
  const { data: categories } = useCategories();
  const [used, setUsed] = useState<Set<string>>(new Set());
  const help = useMutation({
    mutationFn: () => api<Suggestion>("/organizer/writing-help", { method: "POST", body: { title: form.title, description: form.description } }),
    onSuccess: () => setUsed(new Set()),
  });
  const s = help.data;
  const use = (key: string, patch: Partial<EventForm>, field: keyof EventForm) => {
    onApply(patch, field);
    setUsed((u) => new Set(u).add(key));
  };
  const tooShort = form.description.trim().length < 20;

  const rows: { key: string; label: string; value: string; apply: () => void }[] = [];
  if (s) {
    if (s.title && s.title !== form.title) rows.push({ key: "title", label: "Title", value: s.title, apply: () => use("title", { title: s.title! }, "title") });
    if (s.event_type && s.event_type !== form.event_type)
      rows.push({ key: "type", label: "Type", value: typeLabel(s.event_type), apply: () => use("type", { event_type: s.event_type!, category: typeLabel(s.event_type!) }, "event_type") });
    if (s.category && s.category !== form.category_slug)
      rows.push({ key: "category", label: "Category", value: categories?.find((c) => c.slug === s.category)?.name ?? s.category,
        apply: () => use("category", { category_slug: s.category }, "category_slug") });
    const newTags = s.tags.filter((t) => !form.tags.includes(t));
    if (newTags.length)
      rows.push({ key: "tags", label: "Topics", value: s.tags.map((t) => INTERESTS.find((i) => i.id === t)?.label ?? t).join(", "),
        apply: () => use("tags", { tags: s.tags.slice(0, 4) }, "tags") });
  }
  const descChanged = s && s.description && s.description !== form.description;

  return (
    <div>
      <Button type="button" size="sm" variant="secondary" loading={help.isPending} disabled={tooShort} onClick={() => help.mutate()}>
        <Sparkles className="size-4" aria-hidden /> Help me write
      </Button>
      {tooShort && <span className="footnote ml-2 text-text-2">Write a sentence or two first.</span>}
      {help.isError && <p className="callout mt-2 text-danger-text">{(help.error as Error).message}</p>}
      {s && (
        <div className="card mt-3 p-4" aria-live="polite">
          <div className="flex items-start justify-between gap-3">
            <p className="headline">Suggestions</p>
            <button type="button" onClick={() => help.reset()} aria-label="Close suggestions" className="pressable -m-2 grid size-11 place-items-center rounded-full text-text-2">
              <X className="size-5" aria-hidden />
            </button>
          </div>
          <p className="footnote text-text-2">Check them before using. Your facts stay the same; nothing is saved until you save the event.</p>
          {!descChanged && rows.length === 0 && <p className="callout mt-3 text-text-2">Looks good already. Nothing to change.</p>}
          {descChanged && (
            <div className="mt-3">
              <p className="footnote font-medium text-text-2">Description</p>
              <p className="callout mt-1 max-h-48 overflow-y-auto whitespace-pre-line rounded-[14px] bg-text/6 p-3">{s.description}</p>
              <UseButton done={used.has("description")} onClick={() => use("description", { description: s.description }, "description")} />
            </div>
          )}
          {rows.map((r) => (
            <div key={r.key} className="mt-3 flex items-center justify-between gap-3 border-t border-line pt-3">
              <div className="min-w-0">
                <p className="footnote font-medium text-text-2">{r.label}</p>
                <p className="callout">{r.value}</p>
              </div>
              <UseButton done={used.has(r.key)} onClick={r.apply} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UseButton({ done, onClick }: { done: boolean; onClick: () => void }) {
  return (
    <Button type="button" size="sm" variant={done ? "quiet" : "secondary"} disabled={done} onClick={onClick} className="shrink-0">
      {done ? <><Check className="size-4" aria-hidden /> Used</> : "Use"}
    </Button>
  );
}
