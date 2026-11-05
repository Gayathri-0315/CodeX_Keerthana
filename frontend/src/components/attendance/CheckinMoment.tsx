import { AnimatePresence, m, useReducedMotion } from "motion/react";
import { useEffect, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { haptic, spring } from "../../lib/motion";

type Moment = { title: string } | null;
let current: Moment = null;
const listeners = new Set<() => void>();
const set = (v: Moment) => {
  current = v;
  listeners.forEach((l) => l());
};

/** Called when the organizer checks this student in (live, over /api/stream). */
export function showCheckinMoment(title: string) {
  set({ title });
}

/** A short full-screen "You're in" moment: a check mark draws itself, then it fades away after 2 s. */
export function CheckinMoment() {
  const moment = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
    () => current,
  );
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!moment) return;
    haptic(12);
    const t = window.setTimeout(() => set(null), 2000);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && set(null);
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [moment]);

  return createPortal(
    <AnimatePresence>
      {moment && (
        <m.button
          type="button"
          onClick={() => set(null)}
          aria-label="Close"
          className="fixed inset-0 z-[80] grid place-items-center bg-[#0b1f17]/92 px-8 text-center text-white"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <div role="status" aria-live="assertive">
            <m.svg viewBox="0 0 96 96" className="mx-auto size-28" initial={reduced ? false : { scale: 0.85 }} animate={{ scale: 1 }} transition={spring} aria-hidden>
              <circle cx="48" cy="48" r="44" fill="#30d158" />
              <m.path
                d="M28 49l13 13 27-29"
                fill="none"
                stroke="#fff"
                strokeWidth="8"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={reduced ? false : { pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
              />
            </m.svg>
            <p className="mt-6 text-[34px] font-semibold leading-tight tracking-[-0.02em]">You're in. Enjoy it.</p>
            <p className="body mt-2 text-white/80">{moment.title}</p>
          </div>
        </m.button>
      )}
    </AnimatePresence>,
    document.body,
  );
}
