import { lazy, Suspense, useState } from "react";
import { periodOf, useRecap } from "./recapData";

// The viewer (and html-to-image inside it) loads only when opened: nothing added to the normal app load.
const RecapViewer = lazy(() => import("./RecapViewer"));

/** Top of the Record segment: shown once the student has a checked-in event this half year. */
export function RecapCard() {
  const { data } = useRecap(periodOf());
  const [open, setOpen] = useState(false);
  if (!data || data.events_attended === 0) return null;
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        onPointerEnter={() => void import("./RecapViewer")}
        className="pressable liftable mb-4 flex w-full items-center justify-between gap-4 overflow-hidden rounded-[22px] p-5 text-left text-white"
        style={{ background: "linear-gradient(135deg, #0057b8 0%, #6d28d9 60%, #be185d 100%)" }}
      >
        <span>
          <span className="block text-[13px] font-semibold text-white/85">{data.period_label}</span>
          <span className="headline block">Your semester in events</span>
        </span>
        <span className="shrink-0 rounded-full bg-white px-4 py-2 callout font-semibold text-[#1e1b4b]">View recap</span>
      </button>
      {open && (
        <Suspense fallback={<div className="fixed inset-0 z-[85] bg-black/85" aria-busy="true" />}>
          <RecapViewer onClose={() => setOpen(false)} />
        </Suspense>
      )}
    </>
  );
}
