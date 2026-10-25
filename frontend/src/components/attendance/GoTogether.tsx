import { Copy, Share, UserPlus, Users } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { useCreateInvite } from "../../lib/attendance";
import type { Companion } from "../../lib/types";
import { Button } from "../ui/Button";
import { Sheet } from "../ui/Sheet";
import { useToast } from "../ui/Toaster";

const QR = lazy(() => import("qrcode.react").then((m) => ({ default: m.QRCodeSVG })));

export function namesText(names: string[]) {
  if (names.length <= 1) return names[0] ?? "";
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names[0]} and ${names.length - 1} others`;
}

/** "3 from IT, year 3 are going": an aggregate count, never names. */
export function ClassmatesLine({ c, className = "" }: { c: { count: number; label: string } | null; className?: string }) {
  if (!c || c.count < 1) return null;
  return (
    <p className={`footnote flex items-center gap-1.5 text-text-2 ${className}`}>
      <Users className="size-3.5 shrink-0 text-accent" aria-hidden />
      {c.count} from {c.label} {c.count === 1 ? "is" : "are"} going
    </p>
  );
}

/** On the event page once you're registered: who you're going with, and a way to bring someone. */
export function GoTogetherCard({ registrationId, companions, eventTitle }: { registrationId: string; companions: Companion[]; eventTitle: string }) {
  const [open, setOpen] = useState(false);
  const names = companions.map((c) => c.name);
  return (
    <section className="card mt-6 flex items-center gap-4 p-5">
      <div className="flex -space-x-2" aria-hidden>
        {names.length ? (
          names.slice(0, 3).map((n) => (
            <span key={n} className="grid size-10 place-items-center rounded-full bg-accent-soft headline text-accent ring-2 ring-surface">{n[0]}</span>
          ))
        ) : (
          <span className="grid size-10 place-items-center rounded-full bg-accent-soft text-accent"><UserPlus className="size-5" /></span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="headline">{names.length ? `Going with ${namesText(names)}` : "Go together"}</p>
        <p className="callout text-text-2">
          {names.length ? "You'll each see the other's plans, and hear if someone can't make it." : "It's easier to actually go when a friend is going too."}
        </p>
      </div>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <UserPlus className="size-4" aria-hidden /> {names.length ? "Invite more" : "Bring a friend"}
      </Button>
      <BringFriendSheet registrationId={registrationId} eventTitle={eventTitle} open={open} onClose={() => setOpen(false)} />
    </section>
  );
}

export function BringFriendSheet({ registrationId, eventTitle, open, onClose }: { registrationId: string; eventTitle: string; open: boolean; onClose: () => void }) {
  const create = useCreateInvite();
  const toast = useToast();
  const [link, setLink] = useState<string | null>(null);

  useEffect(() => {
    if (open && !link && !create.isPending) {
      create.mutate(registrationId, {
        onSuccess: (r) => setLink(r.url),
        onError: (e) => toast({ tone: "error", title: "Couldn't create an invite", body: (e as Error).message }),
      });
    }
  }, [open]); // create the link once, the first time the sheet opens

  const message = `I'm going to ${eventTitle}. Come with me?`;
  const share = async () => {
    if (!link) return;
    try {
      if (navigator.share) await navigator.share({ title: eventTitle, text: message, url: link });
      else {
        await navigator.clipboard.writeText(`${message} ${link}`);
        toast({ tone: "success", title: "Invite copied", body: "Paste it in your class group or a chat." });
      }
    } catch {
      /* closed the share sheet */
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Bring a friend">
      <p className="callout text-text-2">They tap the link, register in one step, and your passes are linked. You'll both get each other's name in the leave-by reminder.</p>
      <div className="mt-5 flex flex-col items-center">
        <div className="grid size-[200px] place-items-center rounded-[18px] bg-white p-3 shadow-[inset_0_0_0_1px_rgba(0,0,0,0.08)]">
          {link ? (
            <Suspense fallback={<div className="size-[176px] animate-pulse rounded-lg bg-black/5" />}>
              <QR value={link} size={176} marginSize={0} title="Invite link" />
            </Suspense>
          ) : (
            <div className="size-[176px] animate-pulse rounded-lg bg-black/5" />
          )}
        </div>
        <p className="footnote mt-2 text-text-2">Or let them scan this</p>
        {link && <p className="footnote mt-1 max-w-full break-all text-center font-mono text-text-2">{link}</p>}
      </div>
      <div className="mt-5 flex flex-col gap-2">
        <Button size="lg" full onClick={share} disabled={!link}>
          <Share className="size-5" aria-hidden /> Share invite
        </Button>
        <Button
          size="lg"
          variant="quiet"
          full
          disabled={!link}
          onClick={() => link && navigator.clipboard.writeText(link).then(() => toast({ tone: "success", title: "Link copied" }))}
        >
          <Copy className="size-5" aria-hidden /> Copy link
        </Button>
      </div>
    </Sheet>
  );
}
