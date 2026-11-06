import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Tag } from "../../components/ui/Chip";
import { useToast } from "../../components/ui/Toaster";
import { api } from "../../lib/api";
import { OrganizerSheet } from "./AdminData";

type Trust = "new" | "verified" | "trusted";
type Org = {
  id: string; name: string; slug: string | null; email: string; college_or_company: string | null; city: string | null;
  trust_level: Trust; events: number; joined: string;
};

const LABEL: Record<Trust, { text: string; tone: "neutral" | "success" }> = {
  new: { text: "Not verified", tone: "neutral" },
  verified: { text: "Verified", tone: "success" },
  trusted: { text: "Trusted", tone: "success" },
};

/** Every organizer, unverified first, with a one-tap Make verified. */
export function OrganizersAdmin() {
  const qc = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    const t = window.setTimeout(() => setQ(text.trim()), 250);
    return () => window.clearTimeout(t);
  }, [text]);
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["admin", "organizers", q],
    queryFn: () => api<{ items: Org[] }>(`/admin/organizers${q ? `?q=${encodeURIComponent(q)}` : ""}`).then((r) => r.items),
    placeholderData: (prev) => prev,
  });
  const change = useMutation({
    mutationFn: ({ id, level }: { id: string; level: Trust }) => api<{ trust_level: Trust }>(`/admin/organizers/${id}/trust`, { method: "POST", body: { level } }),
    onSuccess: (r, { id }) => {
      qc.setQueriesData<Org[]>({ queryKey: ["admin", "organizers"] }, (list) => list?.map((o) => (o.id === id ? { ...o, trust_level: r.trust_level } : o)));
      qc.invalidateQueries({ queryKey: ["admin", "verification"] });
      toast({ tone: "success", title: r.trust_level === "new" ? "Verification removed" : "Organizer verified",
        body: r.trust_level === "new" ? undefined : "Their events now show the Verified organizer badge." });
    },
    onError: (e) => toast({ tone: "error", title: "Couldn't save", body: (e as Error).message }),
  });

  return (
    <section aria-label="Organizers">
      <label className="relative mb-4 block">
        <span className="sr-only">Search organizers</span>
        <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
        <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search by name, email or college" maxLength={100}
          className="h-12 w-full rounded-[14px] bg-surface pl-11 pr-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]" />
      </label>
      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load organizers.</p>
          <button onClick={() => refetch()} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-48 rounded-[22px]" />
      ) : data.length === 0 ? (
        <div className="card p-8 text-center"><p className="headline">No organizers match.</p></div>
      ) : (
        <ul className="card divide-y divide-line px-5">
          {data.map((o) => {
            const verified = o.trust_level !== "new";
            const busy = change.isPending && change.variables?.id === o.id;
            return (
              <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <button onClick={() => setOpen(o.id)} className="headline text-left hover:text-accent">{o.name}</button>
                    <Tag tone={LABEL[o.trust_level].tone}>{verified && <BadgeCheck className="size-3.5" aria-hidden />}{LABEL[o.trust_level].text}</Tag>
                  </div>
                  <p className="footnote mt-0.5 break-all text-text-2">
                    {[o.email, o.college_or_company, o.city, `${o.events} live event${o.events === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}
                  </p>
                </div>
                {verified ? (
                  <Button size="sm" variant="quiet" loading={busy} onClick={() => change.mutate({ id: o.id, level: "new" })}>Remove verified</Button>
                ) : (
                  <Button size="sm" loading={busy} onClick={() => change.mutate({ id: o.id, level: "verified" })}>
                    <BadgeCheck className="size-4" aria-hidden /> Make verified
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <OrganizerSheet id={open} onClose={() => setOpen(null)} />
    </section>
  );
}
