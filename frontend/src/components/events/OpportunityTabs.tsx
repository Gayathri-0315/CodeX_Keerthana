import { m } from "motion/react";
import { useId } from "react";
import { spring } from "../../lib/motion";
import type { EventType } from "../../lib/types";

export type TypeTab = EventType | "all";

const TABS: { value: TypeTab; label: string }[] = [
  { value: "all", label: "All" },
  { value: "internship", label: "Internships" },
  { value: "competition", label: "Competitions" },
  { value: "hackathon", label: "Hackathons" },
  { value: "workshop", label: "Workshops" },
  { value: "conference", label: "Conferences" },
  { value: "meetup", label: "Meetups" },
  { value: "webinar", label: "Webinars" },
];

/** Horizontally scrollable type tabs with a sliding underline (item 12). */
export function OpportunityTabs({ value, onChange, className = "" }: { value: TypeTab; onChange: (v: TypeTab) => void; className?: string }) {
  const id = useId();
  return (
    <div className={`no-scrollbar -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0 ${className}`}>
      <div role="tablist" aria-label="Opportunity type" className="flex w-max gap-1 border-b border-line">
        {TABS.map((t) => {
          const active = t.value === value;
          return (
            <button
              key={t.value}
              role="tab"
              aria-selected={active}
              onClick={(e) => {
                onChange(t.value);
                e.currentTarget.scrollIntoView({ behavior: "smooth", inline: "nearest", block: "nearest" });
              }}
              className={`pressable relative min-h-11 whitespace-nowrap px-3 callout font-medium transition-colors ${active ? "text-text" : "text-text-2 hover:text-text"}`}
            >
              {t.label}
              {active && (
                <m.span layoutId={`type-underline-${id}`} transition={spring} className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-accent-fill" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export const typeParam = (t: TypeTab) => (t === "all" ? undefined : t);
