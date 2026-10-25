import { AnimatePresence, m } from "motion/react";
import { CheckCircle2, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { haptic, spring } from "../../lib/motion";

type Tone = "success" | "info" | "error" | "warning";
type Action = { label: string; onClick: () => void };
type Toast = { id: number; title: string; body?: string; tone: Tone; actions: Action[]; icon?: LucideIcon };
type ToastInput = { title: string; body?: string; tone?: Tone; action?: Action; actions?: Action[]; icon?: LucideIcon };

const Ctx = createContext<(t: ToastInput) => void>(() => {});
export const useToast = () => useContext(Ctx);

const ICONS = { success: CheckCircle2, info: Info, error: TriangleAlert, warning: TriangleAlert };
const ICON_COLOR = { success: "text-success", info: "text-accent", error: "text-danger", warning: "text-warning" };

/** Dynamic-Island style toasts: a glass pill that springs down from the top center. Max 2 stacked. */
export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<number, number>());
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setToasts((ts) => ts.filter((t) => t.id !== id));
  }, []);

  const arm = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id));
    timers.current.set(id, window.setTimeout(() => dismiss(id), 6000));
  }, [dismiss]);

  const push = useCallback((input: ToastInput) => {
    const id = ++seq.current;
    const toast: Toast = {
      id,
      title: input.title,
      body: input.body,
      tone: input.tone ?? "info",
      icon: input.icon,
      actions: (input.actions ?? (input.action ? [input.action] : [])).slice(0, 2),
    };
    setToasts((ts) => [...ts, toast].slice(-2));
    if (input.tone === "success") haptic();
    arm(id);
  }, [arm]);

  const value = useMemo(() => push, [push]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 top-0 z-[60] flex flex-col items-center gap-2 px-4"
        style={{ paddingTop: "calc(env(safe-area-inset-top, 0px) + 12px)" }}
        aria-live="polite"
      >
        <AnimatePresence initial={false}>
          {toasts.map((t) => {
            const Icon = t.icon ?? ICONS[t.tone];
            return (
              <m.div
                key={t.id}
                layout
                initial={{ y: -40, opacity: 0, scale: 0.9 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                exit={{ y: -30, opacity: 0, scale: 0.95 }}
                transition={spring}
                drag="y"
                dragConstraints={{ top: 0, bottom: 0 }}
                dragElastic={{ top: 0.6, bottom: 0 }}
                onDragEnd={(_e, info) => info.offset.y < -24 && dismiss(t.id)}
                onPointerEnter={() => window.clearTimeout(timers.current.get(t.id))}
                onPointerLeave={() => arm(t.id)}
                role="status"
                className="glass pointer-events-auto w-full max-w-sm rounded-[28px] px-4 py-3 shadow-[0_10px_40px_rgba(0,0,0,0.18)] ring-1 ring-line"
              >
                <div className="flex items-center gap-3">
                  <m.span initial={{ scale: 0.4, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} transition={{ ...spring, delay: 0.08 }}>
                    <Icon className={`size-6 shrink-0 ${ICON_COLOR[t.tone]}`} aria-hidden />
                  </m.span>
                  <div className="min-w-0 flex-1">
                    <p className="callout font-semibold">{t.title}</p>
                    {t.body && <p className="footnote text-text-2">{t.body}</p>}
                  </div>
                  {t.actions.length === 1 && <ActionButton action={t.actions[0]} onDone={() => dismiss(t.id)} />}
                </div>
                {t.actions.length > 1 && (
                  <div className="mt-2 flex justify-end gap-1 pl-9">
                    {t.actions.map((a, i) => <ActionButton key={a.label} action={a} onDone={() => dismiss(t.id)} primary={i === 0} />)}
                  </div>
                )}
              </m.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}

function ActionButton({ action, onDone, primary = true }: { action: Action; onDone: () => void; primary?: boolean }) {
  return (
    <button
      className={`pressable min-h-11 shrink-0 rounded-full px-3 callout font-semibold ${primary ? "text-accent" : "text-text-2"}`}
      onClick={() => {
        action.onClick();
        onDone();
      }}
    >
      {action.label}
    </button>
  );
}
