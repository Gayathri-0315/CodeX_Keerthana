import { AnimatePresence, m } from "motion/react";
import { Loader2, WifiOff } from "lucide-react";
import { wakeState } from "../lib/api";
import { Component, useSyncExternalStore, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { spring } from "../lib/motion";

function subscribe(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

/** A glass pill at the bottom while the device is offline. */
export function OfflineBanner() {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  return (
    <AnimatePresence>
      {!online && (
        <m.div
          role="status"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          transition={spring}
          className="glass fixed inset-x-0 z-[65] mx-auto flex w-fit max-w-[calc(100%-2rem)] items-center gap-2 rounded-full px-4 py-2.5 callout font-medium shadow-card ring-1 ring-line"
          style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 84px)" }}
        >
          <WifiOff className="size-4 text-warning" aria-hidden />
          You're offline. We'll reconnect when you're back.
        </m.div>
      )}
    </AnimatePresence>
  );
}

/** While the hosting wakes the server from sleep (first request after a quiet spell), say so. */
export function WakeBanner() {
  const waking = useSyncExternalStore(wakeState.subscribe, wakeState.get, () => false);
  return (
    <AnimatePresence>
      {waking && (
        <m.div
          role="status"
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -40, opacity: 0 }}
          transition={spring}
          className="glass fixed inset-x-0 z-[65] mx-auto flex w-fit max-w-[calc(100%-2rem)] items-center gap-2.5 rounded-full px-4 py-2.5 shadow-card ring-1 ring-line"
          style={{ top: "calc(env(safe-area-inset-top, 0px) + 12px)" }}
        >
          <Loader2 className="size-4 shrink-0 animate-spin text-accent" aria-hidden />
          <span className="callout">
            <span className="font-medium">Waking up the server...</span>
            <span className="text-text-2"> This can take up to a minute.</span>
          </span>
        </m.div>
      )}
    </AnimatePresence>
  );
}

/** Catches render errors so one broken screen doesn't blank the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn("Screen crashed", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="grid min-h-dvh place-items-center bg-bg p-6 text-center">
        <div className="max-w-sm">
          <p className="title-3">Something went wrong on this screen.</p>
          <p className="callout mt-2 text-text-2">Reload to try again. Your free time, registrations and settings are saved.</p>
          <button onClick={() => window.location.reload()} className="pressable mt-5 min-h-11 rounded-[14px] bg-accent-fill px-5 font-semibold text-white">
            Reload
          </button>
        </div>
      </div>
    );
  }
}

export function NotFound() {
  return (
    <div className="card mx-auto mt-8 max-w-md p-8 text-center">
      <p className="title-3">This page doesn't exist.</p>
      <p className="callout mt-1 text-text-2">The link may be old, or the event was removed.</p>
      <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Go home</Link>
    </div>
  );
}
