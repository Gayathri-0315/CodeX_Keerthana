import { m } from "motion/react";
import { CircleCheck, Loader2, ShieldAlert, ShieldCheck, Users } from "lucide-react";
import { CountUp } from "../ui/CountUp";
import { spring } from "../../lib/motion";
import type { Preview, Risk } from "../../lib/types";

const TONE = {
  low: { title: "Looks good", icon: ShieldCheck, cls: "bg-success/12 text-success-text" },
  medium: { title: "Will show as unverified", icon: ShieldAlert, cls: "bg-warning/12 text-warning-text" },
  high: { title: "Can't be published like this", icon: ShieldAlert, cls: "bg-danger/12 text-danger-text" },
};

export function TrustPanel({ risk, checking }: { risk: Risk | null; checking: boolean }) {
  if (!risk) {
    return (
      <div className="card flex items-center gap-3 p-5 callout text-text-2">
        {checking ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <ShieldCheck className="size-5" aria-hidden />}
        {checking ? "Running the trust check..." : "We'll check the listing for scams as you fill it in."}
      </div>
    );
  }
  const t = TONE[risk.level];
  const Icon = t.icon;
  return (
    <m.div layout transition={spring} className={`rounded-[22px] p-5 ${t.cls}`} aria-live="polite">
      <div className="flex items-center gap-3">
        <Icon className="size-6 shrink-0" aria-hidden />
        <p className="headline flex-1">{t.title}</p>
        {checking && <Loader2 className="size-4 animate-spin" aria-label="Checking" />}
      </div>
      {risk.level !== "low" && risk.reasons.length > 0 && (
        <ul className="callout mt-3 list-disc space-y-1 pl-9">
          {risk.reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
      {risk.level === "high" && <p className="footnote mt-3 pl-9">Fix these and try again, or appeal after publishing if you think we got it wrong.</p>}
    </m.div>
  );
}

export function ReachPanel({ preview }: { preview: Preview | null }) {
  const reach = preview?.reach;
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
          <Users className="size-5" aria-hidden />
        </span>
        <div>
          {reach?.ready ? (
            <p className="headline">
              About <CountUp value={reach.count} /> {reach.count === 1 ? "student fits" : "students fit"} this event
            </p>
          ) : (
            <p className="headline text-text-2">Add a date and time to see your reach</p>
          )}
          <p className="footnote text-text-2">Free then, close enough, within budget, and a strong match.</p>
        </div>
      </div>
      {reach?.ready && (
        <p className="footnote mt-3 flex flex-wrap gap-x-3 text-text-2 tnum">
          <span>{reach.free} free at this time</span>
          {reach.interest_label && <span>{reach.interested} interested in {reach.interest_label}</span>}
        </p>
      )}
    </div>
  );
}

export function OutcomeHint({ preview }: { preview: Preview | null }) {
  if (!preview) return null;
  const { status } = preview.outcome;
  if (status === "pending_review") return <p className="footnote text-text-2">New organizers' first events are checked by an admin before going live.</p>;
  if (status === "published" && preview.outcome.label === "unverified")
    return <p className="footnote text-text-2">It will go live with an "Unverified" label and won't trigger alerts.</p>;
  if (status === "published") return <p className="footnote flex items-center gap-1 text-success-text"><CircleCheck className="size-4" aria-hidden /> Ready to go live.</p>;
  return null;
}
