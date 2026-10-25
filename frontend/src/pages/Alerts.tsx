import { AnimatePresence, animate, m, useMotionValue, type PanInfo } from "motion/react";
import { Bell } from "lucide-react";
import { useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { useNotificationAction, useNotifications } from "../lib/attendance";
import { formatTime, istParts } from "../lib/format";
import { easeOut, spring } from "../lib/motion";
import type { AppNotification } from "../lib/types";

function dayLabel(iso: string) {
  const d = istParts(new Date(iso));
  const t = istParts(new Date());
  const y = istParts(new Date(Date.now() - 86_400_000));
  if (d.year === t.year && d.month === t.month && d.day === t.day) return "Today";
  if (d.year === y.year && d.month === y.month && d.day === y.day) return "Yesterday";
  return new Date(iso).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}

export default function Alerts() {
  const { data, isPending, isError, refetch } = useNotifications();
  const action = useNotificationAction();
  const items = data?.items ?? [];
  const groups = items.reduce<[string, AppNotification[]][]>((acc, n) => {
    const label = dayLabel(n.created_at);
    const last = acc[acc.length - 1];
    if (last && last[0] === label) last[1].push(n);
    else acc.push([label, [n]]);
    return acc;
  }, []);

  return (
    <>
      <PageHeader
        title="Alerts"
        action={data && data.unread > 0 ? <Button variant="quiet" size="sm" onClick={() => action.mutate({ kind: "read_all" })}>Mark all read</Button> : undefined}
      />
      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load alerts.</p>
          <Button variant="secondary" className="mt-4" onClick={() => refetch()}>Try again</Button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-40 rounded-[22px]" />
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <Bell className="mx-auto size-10 text-text-2" aria-hidden />
          <p className="headline mt-3">You're all caught up.</p>
          <p className="callout mt-1 text-text-2">We'll tell you when an event fits your week. At most a few a week.</p>
          <Link to="/settings" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-soft px-5 font-semibold text-accent">Alert settings</Link>
        </div>
      ) : (
        <div className="mx-auto max-w-2xl">
          {groups.map(([label, list]) => (
            <section key={label} className="mb-6">
              <h2 className="footnote mb-2 px-1 font-semibold uppercase tracking-wide text-text-2">{label}</h2>
              <ul className="card overflow-hidden">
                <AnimatePresence initial={false}>
                  {list.map((n) => (
                    <m.li key={n.id} layout="position" exit={{ opacity: 0 }} transition={spring} className="border-b border-line last:border-b-0">
                      <AlertRow n={n} />
                    </m.li>
                  ))}
                </AnimatePresence>
              </ul>
            </section>
          ))}
          <p className="footnote text-center text-text-2">Swipe an alert left to clear it.</p>
        </div>
      )}
    </>
  );
}

function AlertRow({ n }: { n: AppNotification }) {
  const action = useNotificationAction();
  const navigate = useNavigate();
  const x = useMotionValue(0);
  const dragged = useRef(false);

  const open = () => {
    if (dragged.current) return;
    if (!n.read_at) action.mutate({ id: n.id, kind: "click" });
    if (n.event_id) navigate(n.type === "seat_opened" ? "/my" : `/event/${n.event_id}`);
  };

  const onDragEnd = (_: unknown, info: PanInfo) => {
    if (info.offset.x < -100 || info.velocity.x < -600) {
      animate(x, -window.innerWidth, { duration: 0.2, ease: easeOut }).then(() => action.mutate({ id: n.id, kind: "dismiss" }));
    } else {
      animate(x, 0, { type: "spring", stiffness: 320, damping: 30 });
    }
    window.setTimeout(() => (dragged.current = false), 0);
  };

  return (
    <m.button
      style={{ x }}
      drag="x"
      dragDirectionLock
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={{ left: 0.9, right: 0.05 }}
      onDragStart={() => (dragged.current = true)}
      onDragEnd={onDragEnd}
      onClick={open}
      className="flex w-full items-start gap-3 bg-surface px-5 py-4 text-left hover:bg-text/3"
    >
      <span className={`mt-2 size-2 shrink-0 rounded-full ${n.read_at ? "bg-transparent" : "bg-accent-fill"}`} aria-label={n.read_at ? undefined : "Unread"} />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-3">
          <span className={`callout ${n.read_at ? "font-medium" : "font-semibold"}`}>{n.title}</span>
          <span className="footnote shrink-0 text-text-2 tnum">{formatTime(n.created_at)}</span>
        </span>
        <span className="callout mt-0.5 block text-text-2">{n.body}</span>
      </span>
    </m.button>
  );
}
