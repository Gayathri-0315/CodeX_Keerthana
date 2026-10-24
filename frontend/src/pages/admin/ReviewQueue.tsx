import { Flag } from "lucide-react";
import { PageHeader } from "../../components/AppShell";
import { Button } from "../../components/ui/Button";
import { Tag } from "../../components/ui/Chip";
import { useToast } from "../../components/ui/Toaster";
import { formatFee } from "../../lib/format";
import { STATUS_CHIP, useAdminAction, useReviewQueue } from "../../lib/organizer";
import type { ReviewItem } from "../../lib/types";

export default function ReviewQueue() {
  const { data: items, isPending, isError, refetch } = useReviewQueue();
  return (
    <>
      <PageHeader title="Review queue" subtitle="Events waiting for review, reported events and appeals." />
      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load the queue.</p>
          <button onClick={() => refetch()} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-48 rounded-[22px]" />
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="headline">Nothing to review.</p>
          <p className="callout mt-1 text-text-2">New organizers' first events, reported events and appeals show up here.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-4">
          {items.map((i) => <Item key={i.id} item={i} />)}
        </ul>
      )}
    </>
  );
}

function Item({ item: i }: { item: ReviewItem }) {
  const act = useAdminAction();
  const toast = useToast();
  const run = (kind: "approve" | "reject" | "verify", id: string, done: string) =>
    act.mutate({ kind, id }, {
      onSuccess: () => toast({ tone: "success", title: done }),
      onError: (e) => toast({ tone: "error", title: "Couldn't do that", body: (e as Error).message }),
    });
  const chip = STATUS_CHIP[i.status];

  return (
    <li className="card grid gap-5 p-5 md:grid-cols-[200px_minmax(0,1fr)]">
      {i.poster_url ? (
        <img src={i.poster_url} alt={`Poster for ${i.title}`} className="w-full rounded-[14px] object-cover md:max-h-[270px]" />
      ) : (
        <div className="grid h-24 place-items-center rounded-[14px] bg-surface-2 footnote text-text-2">No poster</div>
      )}
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Tag tone={chip.tone}>{chip.text}</Tag>
          <Tag tone={i.risk_score >= 60 ? "warning" : "neutral"}>Risk {i.risk_score}</Tag>
          {i.reports.length > 0 && <Tag tone="warning"><Flag className="size-3.5" aria-hidden />{i.reports.length} reports</Tag>}
        </div>
        <h2 className="title-3 mt-2">{i.title}</h2>
        <p className="callout text-text-2">
          {i.organizer ? `${i.organizer.name} · ${i.organizer.trust_level} · ${i.organizer.email_domain}` : "No organizer"} · {formatFee(i.fee_inr)}
        </p>
        <p className="callout mt-2 line-clamp-3">{i.description}</p>
        {i.registration_url && <p className="footnote mt-1 break-all text-text-2">Link: {i.registration_url}</p>}

        {i.risk_reasons.length > 0 && (
          <div className="mt-3">
            <p className="footnote font-semibold text-text-2">Trust check</p>
            <ul className="callout list-disc pl-5">{i.risk_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
        {i.reports.length > 0 && (
          <div className="mt-3">
            <p className="footnote font-semibold text-text-2">Reports</p>
            <ul className="callout list-disc pl-5">{i.reports.map((r, n) => <li key={n}>{r.reason}</li>)}</ul>
          </div>
        )}
        {i.appeal_note && (
          <div className="mt-3 rounded-[14px] bg-accent-soft p-3">
            <p className="footnote font-semibold text-accent">Appeal</p>
            <p className="callout">{i.appeal_note}</p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => run("approve", i.id, "Approved and published")} disabled={act.isPending}>Approve</Button>
          <Button variant="danger" onClick={() => run("reject", i.id, "Rejected")} disabled={act.isPending}>Reject</Button>
          {i.organizer && i.organizer.trust_level === "new" && (
            <Button variant="secondary" onClick={() => run("verify", i.organizer!.id, "Organizer verified")} disabled={act.isPending}>Mark organizer verified</Button>
          )}
        </div>
      </div>
    </li>
  );
}
