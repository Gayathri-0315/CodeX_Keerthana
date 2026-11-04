import { AnimatePresence, m } from "motion/react";
import { Check, ExternalLink, Ticket } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { mmss, useCancelRegistration, useConfirmSeat, useMyRegistrations, useRegister } from "../../lib/attendance";
import { haptic, snappy, spring } from "../../lib/motion";
import type { EventDetail, FeedItem, Registration } from "../../lib/types";
import { useNow } from "../../lib/useNow";
import { Button } from "../ui/Button";
import { Sheet } from "../ui/Sheet";
import { useToast } from "../ui/Toaster";
import { PassSheet } from "./PassSheet";

type Phase = "idle" | "loading" | "success" | "error";
const MIN_SPIN_MS = 400;
const CELEBRATE_MS = 900;

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Every registration state for one event: Register / Join waitlist (animated), Confirm seat,
 * View pass + Can't make it, waitlist position, and the organizer-site variant.
 */
export function RegisterAction({ event, compact = false }: { event: FeedItem | EventDetail; compact?: boolean }) {
  const reg = event.registration;
  const register = useRegister();
  const confirm = useConfirmSeat();
  const cancel = useCancelRegistration();
  const mine = useMyRegistrations();
  const toast = useToast();
  const navigate = useNavigate();
  const [pass, setPass] = useState<Registration | null>(null);
  const [celebrating, setCelebrating] = useState<"registered" | "waitlisted" | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const now = useNow(reg?.status === "promoted_pending" ? 1000 : 60_000);
  const external = "registration_url" in event ? event.registration_url : null;

  const celebrate = async (r: Registration, origin: HTMLElement | null) => {
    setCelebrating(r.status === "waitlisted" ? "waitlisted" : "registered");
    haptic();
    if (r.toast) toast({ tone: "success", title: r.toast.title, body: r.toast.body });
    if (origin && r.status !== "waitlisted") {
      const box = origin.getBoundingClientRect();
      import("./confetti").then((c) => c.default({ x: box.left + box.width / 2, y: box.top + box.height / 2 }));
    }
    await wait(CELEBRATE_MS);
    setCelebrating(null);
    setPass(r);
  };

  const run = (external = false) => async (button: HTMLElement | null): Promise<boolean> => {
    const t0 = performance.now();
    try {
      const r = await register.mutateAsync({ eventId: event.id, external });
      await wait(Math.max(0, MIN_SPIN_MS - (performance.now() - t0)));
      void celebrate(r, button);
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.code === "unverified") {
        toast({ tone: "error", title: "Verify your email first", body: "We sent you a 6-digit code.", action: { label: "Enter code", onClick: () => navigate("/verify") } });
      } else {
        toast({ tone: "error", title: "Couldn't register", body: e instanceof ApiError && e.status !== 0 ? e.message : "Check your connection and try again." });
      }
      return false;
    }
  };

  const confirmSeat = (id: string) => async (button: HTMLElement | null) => {
    try {
      const r = await confirm.mutateAsync(id);
      void celebrate({ ...r, toast: { title: "Seat confirmed", body: "It's yours. See you there." } }, button);
      return true;
    } catch (e) {
      toast({ tone: "error", title: "Couldn't confirm", body: (e as Error).message });
      return false;
    }
  };

  const openPass = () => {
    const all = [...(mine.data?.upcoming ?? []), ...(mine.data?.waitlist ?? [])];
    const found = all.find((r) => r.event.id === event.id);
    if (found) setPass(found);
  };

  const sheets = (
    <>
      <PassSheet reg={pass} open={!!pass} onClose={() => setPass(null)} />
      <Sheet open={confirmCancel} onClose={() => setConfirmCancel(false)} title="Can't make it?">
        <p className="callout text-text-2">
          {reg?.status === "waitlisted" ? "You'll leave the waitlist for this event." : "Free up your seat for someone on the waitlist?"}
        </p>
        <div className="mt-6 flex flex-col gap-2">
          <Button
            variant="danger"
            size="lg"
            full
            loading={cancel.isPending}
            onClick={() =>
              reg &&
              cancel.mutate(reg.id, {
                onSuccess: () => {
                  setConfirmCancel(false);
                  setPass(null);
                  toast({ tone: "success", title: "Seat released", body: "Thanks for freeing it up. Someone's going to love that." });
                },
                onError: (e) => toast({ tone: "error", title: "Couldn't release your seat", body: (e as Error).message }),
              })
            }
          >
            {reg?.status === "waitlisted" ? "Leave waitlist" : "Release my seat"}
          </Button>
          <Button variant="quiet" size="lg" full onClick={() => setConfirmCancel(false)}>Keep it</Button>
        </div>
      </Sheet>
    </>
  );

  // Keep the success animation on screen while the refetch flips the state underneath.
  if (celebrating) {
    return (
      <>
        <AnimatedButton phaseOverride="success" tone={celebrating === "waitlisted" ? "warning" : "success"} label="" compact={compact} />
        {sheets}
      </>
    );
  }

  if (reg?.status === "promoted_pending" && reg.promotion_expires_at) {
    return (
      <>
        <AnimatedButton label={`Confirm seat · ${mmss(reg.promotion_expires_at, now)}`} onRun={confirmSeat(reg.id)} compact={compact} />
        {sheets}
      </>
    );
  }

  if (reg && (reg.status === "registered" || reg.status === "attended")) {
    return (
      <>
        <div className="flex items-center gap-2">
          {!compact && reg.status === "registered" && (
            <Button variant="quiet" onClick={() => setConfirmCancel(true)}>Can't make it</Button>
          )}
          <Button variant="secondary" size={compact ? "sm" : "md"} onClick={openPass}>
            <Ticket className="size-4" aria-hidden /> View pass
          </Button>
        </div>
        {sheets}
      </>
    );
  }

  if (reg?.status === "waitlisted") {
    return (
      <>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-warning/15 px-3 py-2 callout font-semibold text-warning-text tnum">Waitlist #{reg.waitlist_position}</span>
          {!compact && <Button variant="quiet" onClick={() => setConfirmCancel(true)}>Leave</Button>}
        </div>
        {sheets}
      </>
    );
  }

  if (external && !compact) {
    return (
      <div className="flex items-center gap-2">
        <AnimatedButton label="I registered" variant="secondary" onRun={run(true)} />
        <a href={external} target="_blank" rel="noopener noreferrer" className="pressable inline-flex h-11 items-center gap-1.5 rounded-[14px] bg-accent-fill px-4 font-semibold text-white">
          Organizer's site <ExternalLink className="size-4" aria-hidden />
        </a>
        {sheets}
      </div>
    );
  }

  const next = "next_waitlist_position" in event ? event.next_waitlist_position : undefined;
  return (
    <>
      <div className="flex flex-col items-end">
        <AnimatedButton label={event.waitlist ? "Join waitlist" : "Register"} onRun={run()} compact={compact} variant={event.waitlist ? "secondary" : "primary"} />
        {!compact && event.waitlist && next && <span className="footnote mt-0.5 text-text-2 tnum">You'd be #{next}</span>}
      </div>
      {sheets}
    </>
  );
}

type AnimatedProps = {
  label: string;
  onRun?: (button: HTMLElement | null) => Promise<boolean>;
  compact?: boolean;
  variant?: "primary" | "secondary";
  tone?: "success" | "warning";
  phaseOverride?: Phase;
};

/** Button -> progress ring -> drawn check (SPEC 8.5). Only transform and opacity animate. */
function AnimatedButton({ label, onRun, compact, variant = "primary", tone = "success", phaseOverride }: AnimatedProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const ref = useRef<HTMLButtonElement>(null);
  const shown = phaseOverride ?? phase;
  const round = shown === "loading" || shown === "success";
  const h = compact ? 44 : 48;

  const click = async () => {
    if (!onRun || phase !== "idle") return;
    setPhase("loading");
    const ok = await onRun(ref.current);
    if (!ok) {
      setPhase("error");
      await wait(450);
      setPhase("idle");
    }
    // On success the parent swaps this button for the celebration copy.
  };

  const bg = shown === "success" ? (tone === "warning" ? "bg-warning" : "bg-success") : variant === "primary" ? "bg-accent-fill" : "bg-accent-soft";
  const fg = shown === "success" || variant === "primary" ? "text-white" : "text-accent";

  return (
    <div className="relative inline-grid place-items-center">
      {shown === "success" && (
        <m.span
          aria-hidden
          className={`absolute rounded-full ${tone === "warning" ? "bg-warning" : "bg-success"}`}
          style={{ width: h, height: h }}
          initial={{ scale: 1, opacity: 0.45 }}
          animate={{ scale: 2.4, opacity: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      )}
      <m.button
        ref={ref}
        layout
        type="button"
        onClick={click}
        disabled={shown !== "idle"}
        aria-busy={shown === "loading"}
        aria-label={shown === "success" ? "Done" : label}
        whileTap={{ scale: 0.97 }}
        animate={shown === "error" ? { x: [0, -8, 8, -5, 5, 0] } : { x: 0 }}
        transition={{ layout: spring, x: { duration: 0.4 }, scale: snappy }}
        style={{ borderRadius: round ? h / 2 : 14, height: h, width: round ? h : undefined }}
        className={`relative grid place-items-center overflow-hidden font-semibold transition-colors duration-200 ${bg} ${fg} ${round ? "" : compact ? "px-4 text-[15px]" : "px-6 text-[17px]"}`}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          {shown === "idle" || shown === "error" ? (
            <m.span key="label" layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }} className="whitespace-nowrap tnum">
              {label}
            </m.span>
          ) : shown === "loading" ? (
            <m.svg key="ring" viewBox="0 0 24 24" className="size-6" initial={{ opacity: 0 }} animate={{ opacity: 1, rotate: 360 }} exit={{ opacity: 0 }}
              transition={{ opacity: { duration: 0.12 }, rotate: { repeat: Infinity, duration: 0.8, ease: "linear" } }}>
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="2.5" fill="none" />
              <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fill="none" />
            </m.svg>
          ) : (
            <m.svg key="check" viewBox="0 0 24 24" className="size-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <m.path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth={2.8} strokeLinecap="round" strokeLinejoin="round"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ type: "spring", stiffness: 260, damping: 24, duration: 0.35 }} />
            </m.svg>
          )}
        </AnimatePresence>
      </m.button>
    </div>
  );
}

export function RegisteredChip({ status, position }: { status: string; position: number | null }) {
  if (status === "waitlisted") return <span className="footnote font-semibold text-warning-text tnum">Waitlist #{position}</span>;
  return (
    <span className="inline-flex items-center gap-1 footnote font-semibold text-success-text">
      <Check className="size-3.5" aria-hidden /> Registered
    </span>
  );
}
