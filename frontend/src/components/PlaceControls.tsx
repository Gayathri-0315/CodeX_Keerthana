import { Check, Search } from "lucide-react";
import { useState } from "react";
import { BUDGETS } from "../lib/constants";
import { useAreas } from "../lib/queries";
import type { Area } from "../lib/types";

export function AreaPicker({ value, onChange }: { value: Area | null; onChange: (a: Area) => void }) {
  const [q, setQ] = useState("");
  const { data: areas = [] } = useAreas(q);
  const shown = areas.slice(0, q ? 8 : 6);

  return (
    <div>
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
        <input
          type="search"
          aria-label="Search your area"
          placeholder={value ? value.name : "Search Coimbatore areas"}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="h-12 w-full rounded-[14px] bg-surface pl-11 pr-4 body shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-2" role="listbox" aria-label="Areas">
        {shown.map((a) => {
          const selected = value?.name === a.name;
          return (
            <button
              key={a.name}
              role="option"
              aria-selected={selected}
              onClick={() => {
                onChange(a);
                setQ("");
              }}
              className={`pressable inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 callout font-medium ${
                selected ? "bg-accent text-white" : "bg-surface shadow-[inset_0_0_0_1px_var(--line)]"
              }`}
            >
              {selected && <Check className="size-4" aria-hidden />}
              {a.name}
            </button>
          );
        })}
        {value && !shown.some((a) => a.name === value.name) && (
          <span className="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-accent px-4 callout font-medium text-white">
            <Check className="size-4" aria-hidden /> {value.name}
          </span>
        )}
        {q && shown.length === 0 && <p className="callout py-2 text-text-2">No areas match "{q}". Try a nearby area.</p>}
      </div>
    </div>
  );
}

export function DistanceSlider({ value, onChange, onCommit }: { value: number; onChange: (v: number) => void; onCommit?: (v: number) => void }) {
  const pct = ((value - 5) / 45) * 100;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <label htmlFor="distance" className="footnote font-medium text-text-2">How far will you travel?</label>
        <span className="headline tnum">{value} km</span>
      </div>
      <input
        id="distance"
        type="range"
        min={5}
        max={50}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        onPointerUp={(e) => onCommit?.(Number((e.target as HTMLInputElement).value))}
        onKeyUp={(e) => onCommit?.(Number((e.target as HTMLInputElement).value))}
        className="slider"
        style={{ ["--pct" as string]: `${pct}%` }}
      />
    </div>
  );
}

export function BudgetPicker({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  return (
    <div>
      <p id="budget-label" className="footnote mb-1.5 font-medium text-text-2">Budget per event</p>
      <div role="radiogroup" aria-labelledby="budget-label" className="grid grid-cols-5 gap-1 rounded-[14px] bg-text/6 p-1">
        {BUDGETS.map((b) => {
          const active = b.value === value;
          return (
            <button
              key={b.label}
              role="radio"
              aria-checked={active}
              onClick={() => onChange(b.value)}
              className={`pressable min-h-11 rounded-[10px] callout font-medium tnum transition-colors ${active ? "bg-surface text-text shadow-[0_1px_3px_rgba(0,0,0,0.12)]" : "text-text-2"}`}
            >
              {b.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
