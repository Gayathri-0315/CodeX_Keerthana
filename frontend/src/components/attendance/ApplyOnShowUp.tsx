import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { openAuth, showRoleNotice } from "../../lib/authModal";
import { useMe } from "../../lib/queries";
import type { EventDetail } from "../../lib/types";
import { Button } from "../ui/Button";
import { Sheet } from "../ui/Sheet";
import { useToast } from "../ui/Toaster";

const inputCls =
  "w-full rounded-[14px] bg-surface px-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]";

/** Apply for an internship on ShowUp (the organizer gave no outside link): a short note and an optional link. */
export function ApplyOnShowUp({ event: e }: { event: EventDetail }) {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(false);
  const [manage, setManage] = useState(false);
  const [note, setNote] = useState("");
  const [link, setLink] = useState("");
  const [error, setError] = useState<string | null>(null);
  const applied = e.application;
  const closed = new Date(e.start_at).getTime() < Date.now();

  // Back from signing in to apply: open the form straight away.
  useEffect(() => {
    if (params.get("apply") === "1" && me?.role === "student" && !applied) setOpen(true);
    if (params.has("apply")) setParams((p) => { p.delete("apply"); return p; }, { replace: true });
  }, [me?.role]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = () => qc.invalidateQueries({ queryKey: ["event", e.id] });
  const send = useMutation({
    mutationFn: () => api(`/events/${e.id}/apply`, { method: "POST", body: { note: note.trim(), link: link.trim() || null } }),
    onSuccess: () => {
      setOpen(false);
      toast({ tone: "success", title: "Application sent", body: `${e.organizer?.name ?? "The organizer"} will reply by email.` });
      refresh();
    },
    onError: (err) => setError((err as Error).message),
  });
  const withdraw = useMutation({
    mutationFn: () => api(`/events/${e.id}/apply`, { method: "DELETE" }),
    onSuccess: () => {
      setManage(false);
      toast({ tone: "success", title: "Application withdrawn" });
      refresh();
    },
    onError: (err) => toast({ tone: "error", title: "That didn't work", body: (err as Error).message }),
  });

  const start = () => {
    if (!me) return openAuth({ audience: "student", intent: { kind: "navigate", to: `/event/${e.id}?apply=1` } });
    if (me.role !== "student") return showRoleNotice("organizer_cannot_register");
    setError(null);
    setOpen(true);
  };

  return (
    <>
      {applied ? (
        <Button size="lg" variant="secondary" onClick={() => setManage(true)}>
          <Check className="size-5" aria-hidden /> Applied
        </Button>
      ) : (
        <Button size="lg" onClick={start} disabled={closed}>{closed ? "Applications closed" : "Apply"}</Button>
      )}

      <Sheet open={open} onClose={() => setOpen(false)} title="Apply">
        <form
          className="flex flex-col gap-4 pb-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            setError(null);
            send.mutate();
          }}
        >
          <p className="callout text-text-2">
            Your application goes to {e.organizer?.name ?? "the organizer"} with your name and email, so they can reply.
          </p>
          <div>
            <label htmlFor="apply-note" className="footnote mb-1.5 block font-medium text-text-2">Why are you interested?</label>
            <textarea id="apply-note" value={note} onChange={(x) => setNote(x.target.value)} rows={5} minLength={20} maxLength={1000} required
              placeholder="A few lines about you, what you've done and why this internship fits."
              className={`${inputCls} py-3`} />
            <p className="footnote mt-1 text-right text-text-2 tnum">{note.trim().length < 20 ? `${20 - note.trim().length} more characters` : `${note.length}/1000`}</p>
          </div>
          <div>
            <label htmlFor="apply-link" className="footnote mb-1.5 block font-medium text-text-2">Portfolio, resume or GitHub link (optional)</label>
            <input id="apply-link" type="url" inputMode="url" value={link} onChange={(x) => setLink(x.target.value)} maxLength={500}
              placeholder="https://" className={`${inputCls} h-12`} />
          </div>
          {error && <p role="alert" className="callout text-danger-text">{error}</p>}
          <Button size="lg" full type="submit" loading={send.isPending} disabled={note.trim().length < 20}>
            <Send className="size-4" aria-hidden /> Send application
          </Button>
        </form>
      </Sheet>

      <Sheet open={manage} onClose={() => setManage(false)} title="Your application">
        <div className="flex flex-col gap-3 pb-2">
          <p className="body">
            Sent {applied ? new Date(applied.at).toLocaleDateString([], { day: "numeric", month: "short" }) : ""}. {e.organizer?.name ?? "The organizer"} will reply by email.
          </p>
          {!closed && (
            <Button variant="danger" full loading={withdraw.isPending} onClick={() => withdraw.mutate()}>Withdraw application</Button>
          )}
        </div>
      </Sheet>
    </>
  );
}
