import { Lock, Megaphone, MessagesSquare } from "lucide-react";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";
import { chatListTime, nameHue, useMyChats, type ChatListItem } from "../lib/chat";
import { useMe } from "../lib/queries";

/** Every event group chat I'm in, newest first, like a messaging app's chat list. */
export default function ChatsPage() {
  const { data: me } = useMe();
  const { data, isPending, isError, refetch } = useMyChats(!!me);
  const host = me?.role === "organizer";

  return (
    <>
      <PageHeader title="Group chats" subtitle={host ? "One group per event, with everyone going." : "One group per event you're going to, with the host."} />
      <div className="mx-auto max-w-2xl">
        {isError ? (
          <div className="card p-6 text-center">
            <p className="headline">Couldn't load your chats.</p>
            <button onClick={() => refetch()} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
          </div>
        ) : isPending ? (
          <div className="card divide-y divide-line px-4" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3 py-3">
                <div className="skeleton size-12 shrink-0 rounded-full" />
                <div className="flex-1"><div className="skeleton h-4 w-1/2 rounded" /><div className="skeleton mt-2 h-3.5 w-3/4 rounded" /></div>
              </div>
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <div className="card p-8 text-center">
            <span className="mx-auto grid size-14 place-items-center rounded-full bg-accent-soft text-accent"><MessagesSquare className="size-7" aria-hidden /></span>
            <p className="headline mt-4">No group chats yet</p>
            <p className="callout mt-1 text-text-2">
              {host ? "Each published event gets a group chat. People join when they register." : "Register for an event and you'll join its group chat with the host and everyone going."}
            </p>
            {!host && (
              <Link to="/explore" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Find events</Link>
            )}
          </div>
        ) : (
          <ul className="card divide-y divide-line overflow-hidden">
            {data.items.map((c) => <Row key={c.event_id} c={c} />)}
          </ul>
        )}
      </div>
    </>
  );
}

function Row({ c }: { c: ChatListItem }) {
  const unread = c.unread > 0;
  return (
    <li>
      <Link to={`/event/${c.event_id}/chat`} className="pressable flex items-center gap-3 px-4 py-3 hover:bg-text/4">
        <GroupAvatar title={c.title} poster={c.poster_url} id={c.event_id} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className="headline truncate">{c.title}</p>
            {c.last && <span className={`footnote shrink-0 tnum ${unread ? "font-semibold text-accent" : "text-text-2"}`}>{chatListTime(c.last.at)}</span>}
          </div>
          <div className="mt-0.5 flex items-center justify-between gap-3">
            <p className={`callout truncate ${unread ? "text-text" : "text-text-2"}`}>
              {c.read_only && <Lock className="mr-1 inline size-3.5 align-[-2px]" aria-label="Closed" />}
              {c.last ? (
                <>
                  {c.last.announcement && <Megaphone className="mr-1 inline size-3.5 align-[-2px]" aria-label="Announcement" />}
                  <span className="font-medium">{c.last.sender}: </span>{c.last.body}
                </>
              ) : (
                "No messages yet. Say hi!"
              )}
            </p>
            {unread && (
              <span className="grid h-5 min-w-5 shrink-0 place-items-center rounded-full bg-accent-fill px-1.5 text-[12px] font-semibold text-white tnum" aria-label={`${c.unread} unread`}>
                {c.unread > 99 ? "99+" : c.unread}
              </span>
            )}
          </div>
        </div>
      </Link>
    </li>
  );
}

/** The event's poster as the group photo, or its first letter on a steady colour. */
export function GroupAvatar({ title, poster, id, size = "size-12" }: { title: string; poster: string | null; id: string; size?: string }) {
  return poster ? (
    <img src={poster} alt="" className={`${size} shrink-0 rounded-full object-cover`} loading="lazy" />
  ) : (
    <span className={`${size} chat-avatar grid shrink-0 place-items-center rounded-full text-[18px] font-semibold text-white`}
      style={{ "--h": nameHue(id) } as CSSProperties}>
      {title.trim()[0]?.toUpperCase() ?? "#"}
    </span>
  );
}
