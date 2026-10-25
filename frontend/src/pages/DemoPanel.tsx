import { useQueryClient } from "@tanstack/react-query";
import { Megaphone, MapPin, RotateCcw, Ticket } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { useToast } from "../components/ui/Toaster";
import { api } from "../lib/api";
import { keys, useDemoSignIn, useMe } from "../lib/queries";
import type { Role } from "../lib/types";

const ACTIONS = [
  { path: "publish-ai-workshop", icon: Megaphone, title: "Publish AI Workshop now", body: "The demo club publishes a new workshop; fitting students get a match alert." },
  { path: "release-seat", icon: Ticket, title: "Release a seat", body: "Puts the demo student first on Startup Pitch Night's waitlist, then someone cancels." },
  { path: "leave-by", icon: MapPin, title: "Fast-forward to leave-by time", body: "Sends the demo student's next \"Time to head out\" alert now." },
] as const;

/** Hidden helper for live demos (SPEC 12): one tap per step of the demo script. */
export default function DemoPanel() {
  const { data: me } = useMe();
  const demo = useDemoSignIn();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);

  const run = async (path: string, title: string) => {
    setBusy(path);
    try {
      const r = await api<Record<string, unknown>>(`/demo/${path}`, { method: "POST" });
      qc.invalidateQueries();
      const detail = path === "publish-ai-workshop" ? `${r.notified} ${r.notified === 1 ? "student" : "students"} alerted.` : "Done.";
      toast({ tone: "success", title, body: me?.email === "student@demo.app" ? detail : `${detail} Switch to the demo student to see it.` });
    } catch (e) {
      toast({ tone: "error", title: "That didn't work", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    setBusy("reset");
    try {
      await api("/demo/reset", { method: "POST" });
      qc.clear();
      await demo.mutateAsync("student");
      toast({ tone: "success", title: "Demo reset", body: "Fresh data, signed in as the demo student." });
      navigate("/");
    } catch (e) {
      toast({ tone: "error", title: "Couldn't reset", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const switchTo = (role: Role) =>
    demo.mutate(role, {
      onSuccess: () => {
        qc.removeQueries({ predicate: (q) => q.queryKey[0] !== keys.me[0] });
        navigate("/");
      },
    });

  return (
    <>
      <PageHeader title="Demo panel" subtitle={`Signed in as ${me?.email ?? "…"}`} />
      <div className="mx-auto flex max-w-2xl flex-col gap-3">
        {ACTIONS.map((a) => (
          <div key={a.path} className="card flex items-center gap-4 p-5">
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><a.icon className="size-5" aria-hidden /></span>
            <div className="min-w-0 flex-1">
              <p className="headline">{a.title}</p>
              <p className="callout text-text-2">{a.body}</p>
            </div>
            <Button loading={busy === a.path} disabled={!!busy} onClick={() => run(a.path, a.title)}>Run</Button>
          </div>
        ))}
        <div className="card p-5">
          <p className="headline">Switch account</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => switchTo("student")}>Demo student</Button>
            <Button variant="secondary" onClick={() => switchTo("organizer")}>Demo organizer</Button>
            <Button variant="secondary" onClick={() => switchTo("admin")}>Admin</Button>
          </div>
        </div>
        <div className="card flex items-center gap-4 p-5">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-danger/12 text-danger-text"><RotateCcw className="size-5" aria-hidden /></span>
          <div className="min-w-0 flex-1">
            <p className="headline">Reset demo</p>
            <p className="callout text-text-2">Reloads all demo data. Everyone is signed out.</p>
          </div>
          <Button variant="danger" loading={busy === "reset"} disabled={!!busy} onClick={reset}>Reset</Button>
        </div>
      </div>
    </>
  );
}
