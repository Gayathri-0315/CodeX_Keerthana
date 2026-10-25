import { m } from "motion/react";
import { Clock, MapPin, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Thumb } from "../components/events/EventCard";
import { Button } from "../components/ui/Button";
import { Tag } from "../components/ui/Chip";
import { useToast } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { returnTo, useAcceptInvite, useInvite } from "../lib/attendance";
import { formatDayTime, formatFee } from "../lib/format";
import { haptic, spring } from "../lib/motion";
import { useMe } from "../lib/queries";

/** A friend's "Go together" link. Viewable signed out; joining needs an account. */
export default function InvitePage() {
  const { code = "" } = useParams();
  const { data: invite, isPending, error } = useInvite(code);
  const { data: me } = useMe();
  const accept = useAcceptInvite();
  const toast = useToast();
  const navigate = useNavigate();

  const join = () => {
    if (!me) {
      returnTo.set(`/invite/${code}`);
      navigate("/welcome");
      return;
    }
    accept.mutate(code, {
      onSuccess: (r) => {
        haptic();
        if (r.toast) toast({ tone: "success", title: r.toast.title, body: r.toast.body });
        navigate(`/event/${r.event.id}`, { replace: true });
      },
      onError: (e) => toast({ tone: "error", title: "Couldn't join", body: e instanceof ApiError ? e.message : "Check your connection and try again." }),
    });
  };

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-5 pb-10 safe-top">
      <div className="flex h-16 items-center"><Link to="/" aria-label="ShowUp home"><Logo /></Link></div>
      {isPending ? (
        <div className="skeleton mt-6 h-80 rounded-[22px]" aria-busy="true" />
      ) : error || !invite ? (
        <div className="card mt-6 p-8 text-center">
          <p className="headline">This invite doesn't work.</p>
          <p className="callout mt-1 text-text-2">{error instanceof ApiError ? error.message : "Check your connection, then try again."}</p>
          <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Find events</Link>
        </div>
      ) : (
        <m.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
          <p className="callout mt-4 text-text-2">{invite.inviter} invited you</p>
          <h1 className="title-1 mt-1">Go together?</h1>
          <div className="card mt-6 overflow-hidden">
            <Thumb event={{ ...invite.event, id: `invite-${invite.code}` }} large className="aspect-[5/2] w-full rounded-none" />
            <div className="p-5">
              <h2 className="title-3">{invite.event.title}</h2>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {invite.event.start_at && invite.event.end_at && (
                  <Tag tone="accent"><Clock className="size-3.5" aria-hidden />{formatDayTime(invite.event.start_at, invite.event.end_at)}</Tag>
                )}
                <Tag><MapPin className="size-3.5" aria-hidden />{invite.event.mode === "online" ? "Online" : invite.event.venue_name}</Tag>
                <Tag>{formatFee(invite.event.fee_inr)}</Tag>
              </div>
              <p className="callout mt-4 flex items-center gap-2 text-text-2">
                <Users className="size-4 text-accent" aria-hidden />
                {invite.going === 1 ? `${invite.inviter} is going` : `${invite.inviter} and ${invite.going - 1} ${invite.going === 2 ? "friend are" : "friends are"} going`}
              </p>
            </div>
          </div>
          {invite.problem ? (
            <p role="alert" className="callout mt-6 rounded-[14px] bg-warning/12 p-4 text-warning-text">{invite.problem}</p>
          ) : me && me.role !== "student" ? (
            <p className="callout mt-6 text-text-2">Sign in with a student account to join.</p>
          ) : (
            <div className="mt-6 flex flex-col gap-2">
              <Button size="lg" full loading={accept.isPending} onClick={join}>
                {me ? `Go with ${invite.inviter}` : "Sign in to go together"}
              </Button>
              <p className="footnote text-center text-text-2">You'll be registered and your passes linked. You can cancel any time.</p>
            </div>
          )}
        </m.div>
      )}
    </div>
  );
}
