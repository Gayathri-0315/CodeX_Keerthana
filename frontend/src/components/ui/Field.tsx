import { forwardRef, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string };

export const Field = forwardRef<HTMLInputElement, Props>(function Field({ label, hint, error, id, className = "", ...rest }, ref) {
  const inputId = id ?? `f-${label.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <div className={className}>
      <label htmlFor={inputId} className="footnote mb-1.5 block font-medium text-text-2">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={!!error || undefined}
        aria-describedby={error || hint ? `${inputId}-msg` : undefined}
        className="h-12 w-full rounded-[14px] bg-surface px-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none transition-shadow placeholder:text-text-2/70 focus:shadow-[inset_0_0_0_2px_var(--accent)] aria-invalid:shadow-[inset_0_0_0_2px_var(--danger)]"
        {...rest}
      />
      {(error || hint) && (
        <p id={`${inputId}-msg`} className={`footnote mt-1.5 ${error ? "text-danger-text" : "text-text-2"}`}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
});
