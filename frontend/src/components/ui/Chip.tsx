import { m } from "motion/react";
import { Check } from "lucide-react";
import { snappy } from "../../lib/motion";

type Props = {
  label: string;
  selected: boolean;
  onToggle: () => void;
};

export function Chip({ label, selected, onToggle }: Props) {
  return (
    <m.button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      whileTap={{ scale: 0.92 }}
      animate={{ scale: 1 }}
      transition={snappy}
      className={`inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 callout font-medium transition-colors duration-200 ${
        selected ? "bg-accent text-white" : "bg-surface text-text shadow-[inset_0_0_0_1px_var(--line)]"
      }`}
    >
      {selected && <Check className="size-4" strokeWidth={2.5} aria-hidden />}
      {label}
    </m.button>
  );
}

export function Tag({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" | "warning" | "success" }) {
  const tones = {
    neutral: "bg-surface-2 text-text-2 shadow-[inset_0_0_0_1px_var(--line)]",
    accent: "bg-accent-soft text-accent",
    warning: "bg-warning/15 text-warning-text",
    success: "bg-success/15 text-success-text",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 footnote font-medium ${tones[tone]}`}>{children}</span>;
}
