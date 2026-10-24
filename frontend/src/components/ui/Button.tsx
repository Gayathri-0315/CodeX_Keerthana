import { forwardRef, type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "quiet" | "danger";
type Size = "lg" | "md" | "sm";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-white hover:brightness-110",
  secondary: "bg-accent-soft text-accent",
  quiet: "text-accent hover:bg-accent-soft",
  danger: "bg-danger/12 text-danger-text",
};

const sizes: Record<Size, string> = {
  lg: "h-[52px] px-6 text-[17px] rounded-[14px]",
  md: "h-11 px-5 text-[15px] rounded-[14px]",
  sm: "h-11 px-3.5 text-[15px] rounded-full", // 44 px target even when visually small
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  full?: boolean;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", full, loading, className = "", children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={`pressable inline-flex items-center justify-center gap-2 font-semibold select-none disabled:opacity-45 ${variants[variant]} ${sizes[size]} ${full ? "w-full" : ""} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
});

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`size-5 animate-spin ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" fill="none" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fill="none" />
    </svg>
  );
}
