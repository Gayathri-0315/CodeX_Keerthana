import type { Transition } from "motion/react";

export const spring: Transition = { type: "spring", stiffness: 320, damping: 30, mass: 0.9 };
export const gentle: Transition = { type: "spring", stiffness: 200, damping: 26 };
export const snappy: Transition = { type: "spring", stiffness: 500, damping: 32 };
export const easeOut = [0.22, 1, 0.36, 1] as const;

export const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.2, ease: easeOut } },
};

export function haptic(ms = 10) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* unsupported */
  }
}
