import { AnimatePresence, m } from "motion/react";
import { CalendarPlus, Clock, Navigation, Users, X } from "lucide-react";
import { namesText } from "./GoTogether";
import { lazy, Suspense, useEffect } from "react";
import { createPortal } from "react-dom";
import { countdown } from "../../lib/attendance";
import { formatLongDate, formatTime, formatTimeRange } from "../../lib/format";
import { spring } from "../../lib/motion";
import type { Registration } from "../../lib/types";
import { useNow } from "../../lib/useNow";
import { Button } from "../ui/Button";

const QR = lazy(() => import("qrcode.react").then((m) => ({ default: m.QRCodeSVG })));

/** The ticket: slides up from the bottom; white card so the QR scans at any screen brightness. */
export function PassSheet({ reg, open, onClose }: { reg: Registration | null; open: boolean; onClose: () => void }) {
  const now = useNow(30_000);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && reg && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
          <m.div className="absolute inset-0 bg-black/45" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <m.div
            role="dialog"
            aria-modal="true"
            aria-label={`Pass for ${reg.event.title}`}
            className="safe-bottom relative w-full max-w-sm overflow-hidden rounded-t-[28px] bg-white text-[#1d1d1f] shadow-card sm:rounded-[28px]"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%", opacity: 0 }}
            transition={spring}
          >
            <button onClick={onClose} aria-label="Close" className="pressable absolute right-3 top-3 grid size-11 place-items-center rounded-full text-[#6e6e73]">
              <X className="size-5" />
            </button>
            <PassBody reg={reg} now={now} />
            <div className="flex flex-col gap-2 px-6 pb-6">
              <Button size="lg" full onClick={onClose}>Done</Button>
              {/* Secondary on purpose: it's already on the ShowUp calendar. Downloads only when tapped. */}
              <a
                href={`/api/events/${reg.event.id}/ics`}
                className="pressable inline-flex min-h-11 items-center justify-center gap-2 rounded-[14px] callout font-medium text-[#0071e3]"
              >
                <CalendarPlus className="size-4" aria-hidden /> Add to my phone calendar
              </a>
            </div>
          </m.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

function PassBody({ reg, now }: { reg: Registration; now: number }) {
  const e = reg.event;
  const waitlisted = reg.status === "waitlisted";
  return (
    <div className="px-6 pb-4 pt-7 text-center">
      <p className="footnote font-semibold uppercase tracking-wide text-[#6e6e73]">{waitlisted ? "Waitlist" : "Your pass"}</p>
      <h2 className="title-3 mt-1">{e.title}</h2>
      <p className="callout mt-1 text-[#6e6e73]">
        {formatLongDate(e.start_at)} · {formatTimeRange(e.start_at, e.end_at)}
      </p>

      {waitlisted ? (
        <p className="callout mx-auto mt-6 max-w-[26ch] rounded-[16px] bg-[#ff9f0a]/15 p-4 font-medium text-[#a35200]">
          Waitlist #{reg.waitlist_position}. We'll tell you if a seat opens.
        </p>
      ) : (
        <div className="mt-5 flex flex-col items-center">
          <div className="rounded-[18px] border border-black/10 p-3">
            <Suspense fallback={<div className="size-[180px] animate-pulse rounded-lg bg-black/5" />}>
              <QR value={reg.checkin_token} size={180} level="M" marginSize={0} title="Check-in code" />
            </Suspense>
          </div>
          <p className="footnote mt-2 text-[#6e6e73]">
            Code <span className="font-mono font-semibold tracking-widest text-[#1d1d1f]">{reg.checkin_code}</span>
          </p>
        </div>
      )}

      <div className="mt-5 flex flex-col items-center gap-1">
        {reg.companions?.length > 0 && (
          <p className="callout inline-flex items-center gap-1.5 font-medium text-[#0066cc]">
            <Users className="size-4" aria-hidden /> Going with {namesText(reg.companions.map((c) => c.name))}
          </p>
        )}
        <p className="callout inline-flex items-center gap-1.5 font-medium tnum">
          <Clock className="size-4" aria-hidden /> {countdown(e.start_at, now)}
        </p>
        {reg.leave_by && !waitlisted && (
          <p className="headline tnum text-[#0071e3]">Leave by {formatTime(reg.leave_by)}</p>
        )}
        {e.maps_url && !waitlisted && (
          <a href={e.maps_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-1 callout font-medium text-[#0071e3]">
            <Navigation className="size-4" aria-hidden /> Directions to {e.venue_name}
          </a>
        )}
      </div>
    </div>
  );
}
