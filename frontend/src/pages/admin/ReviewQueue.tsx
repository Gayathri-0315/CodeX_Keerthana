import { Flag, Mail } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
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
      <PageHeader title="Review queue" subtitle="Events waiting for review, reported events and appeals." action={<TestEmailButton />} />
      <VerificationRequests />
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

/** Admin-only check that EMAIL_PROVIDER / EMAIL_API_KEY / EMAIL_FROM work. */
function TestEmailButton() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const r = await api<{ status: "sent" | "skipped"; message: string }>("/admin/test-email", { method: "POST" });
      toast({ tone: r.status === "sent" ? "success" : "info", title: r.status === "sent" ? "Test email sent" : "Email skipped", body: r.message });
    } catch (e) {
      toast({ tone: "error", title: "Test email failed", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="secondary" size="sm" loading={busy} onClick={run}>
      <Mail className="size-4" aria-hidden />Send test email to me
    </Button>
  );
}

type VerificationItem = {
  id: string;
  document_type: string;
  note: string;
  submitted_at: string;
  organizer: { id: string; name: string; email: string | null; college_or_company: string | null; faculty_name: string | null; faculty_email: string | null } | null;
};
const DOC_LABEL: Record<string, string> = { college_id: "College ID", faculty_letter: "Faculty letter", company_proof: "Company proof", other: "Other document" };

/** Organizers asking to be verified, with their private document (admins only). */
function VerificationRequests() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data } = useQuery({
    queryKey: ["admin", "verification"],
    queryFn: () => api<{ items: VerificationItem[] }>("/admin/verification-requests").then((r) => r.items),
  });
  const decide = useMutation({
    mutationFn: ({ id, ok }: { id: string; ok: boolean }) => api(`/admin/verification-requests/${id}/${ok ? "approve" : "reject"}`, { method: "POST" }),
    onSuccess: (_r, { ok }) => {
      toast({ tone: "success", title: ok ? "Organizer verified" : "Request declined" });
      qc.invalidateQueries({ queryKey: ["admin", "verification"] });
    },
    onError: (e) => toast({ tone: "error", title: "Couldn't save", body: (e as Error).message }),
  });
  if (!data || data.length === 0) return null;
  return (
    <section className="mb-8">
      <h2 className="footnote mb-2 px-1 font-semibold uppercase tracking-wide text-text-2">Organization verification</h2>
      <ul className="flex flex-col gap-3">
        {data.map((r) => (
          <li key={r.id} className="card p-5">
            <p className="headline">{r.organizer?.name}</p>
            <p className="footnote text-text-2">
              {[r.organizer?.email, r.organizer?.college_or_company, r.organizer?.faculty_name && `Faculty: ${r.organizer.faculty_name}${r.organizer.faculty_email ? ` (${r.organizer.faculty_email})` : ""}`]
                .filter(Boolean).join(" · ")}
            </p>
            <p className="callout mt-2">{DOC_LABEL[r.document_type] ?? r.document_type}{r.note ? `: ${r.note}` : ""}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <a href={`/api/admin/verification-requests/${r.id}/document`} target="_blank" rel="noopener noreferrer"
                className="pressable inline-flex min-h-11 items-center rounded-[14px] bg-accent-soft px-4 callout font-semibold text-accent">View document</a>
              <Button size="sm" onClick={() => decide.mutate({ id: r.id, ok: true })}>Verify</Button>
              <Button size="sm" variant="danger" onClick={() => decide.mutate({ id: r.id, ok: false })}>Decline</Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
