import { m } from "motion/react";
import { useId } from "react";
import { spring } from "../../lib/motion";

type Props<T extends string> = {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  className?: string;
};

export function Segmented<T extends string>({ options, value, onChange, label, className = "" }: Props<T>) {
  const id = useId();
  return (
    <div role="tablist" aria-label={label} className={`inline-flex rounded-full bg-text/6 p-1 ${className}`}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`relative min-h-9 flex-1 whitespace-nowrap rounded-full px-2.5 callout sm:px-4 font-medium transition-colors ${active ? "text-text" : "text-text-2"}`}
          >
            {active && (
              <m.span
                layoutId={`seg-${id}`}
                transition={spring}
                className="absolute inset-0 rounded-full bg-surface shadow-[0_1px_3px_rgba(0,0,0,0.12)]"
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
