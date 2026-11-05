import { useSyncExternalStore } from "react";

export type Side = "student" | "organizer";
export type Mode = "signin" | "signup";
/** Who the popup is for. "unknown" (both panels) is used only by the Sign in button in the top nav. */
export type Audience = Side | "unknown";

/** What the guest was trying to do. After sign-in it runs automatically, so they never tap twice. */
export type Intent =
  | { kind: "register"; eventId: string }
  | { kind: "save"; eventId: string }
  | { kind: "create_event" }
  | { kind: "follow"; slug: string }
  | { kind: "navigate"; to: string };

type State = { open: boolean; audience: Audience; mode: Mode; intent: Intent | null; seq: number };

let state: State = { open: false, audience: "unknown", mode: "signin", intent: null, seq: 0 };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function openAuth(opts: { audience: Audience; mode?: Mode; intent?: Intent | null }) {
  state = { open: true, audience: opts.audience, mode: opts.mode ?? "signin", intent: opts.intent ?? null, seq: state.seq + 1 };
  emit();
}

export function closeAuth() {
  state = { ...state, open: false };
  emit();
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useAuthModal(): State {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

// ---- "wrong account" notice: a signed-in person taps an action meant for the other role ----

export type RoleNotice = "student_needs_organizer" | "organizer_cannot_register" | null;
let notice: RoleNotice = null;
const noticeListeners = new Set<() => void>();

export function showRoleNotice(n: Exclude<RoleNotice, null>) {
  notice = n;
  noticeListeners.forEach((l) => l());
}

export function closeRoleNotice() {
  notice = null;
  noticeListeners.forEach((l) => l());
}

export function useRoleNotice(): RoleNotice {
  return useSyncExternalStore(
    (l) => {
      noticeListeners.add(l);
      return () => noticeListeners.delete(l);
    },
    () => notice,
    () => notice,
  );
}
