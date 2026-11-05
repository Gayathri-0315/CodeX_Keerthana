import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Flag, Lock, Megaphone, MoreHorizontal, Pin, Send, Trash2, Unlock, UserMinus, Users } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Sheet } from "../components/ui/Sheet";
import { useToast } from "../components/ui/Toaster";
import { api, ApiError } from "../lib/api";
import { chatKeys, type ChatMessage, type ChatRoom } from "../lib/chat";
import { formatDayTime, formatTime } from "../lib/format";

const REPORT_REASONS = ["Spam or selling", "Scam or asking for money", "Rude or harassing", "Something else"];

/** The event group chat: the host and the people going. */
export default function EventChat() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [announce, setAnnounce] = useState(false);
  const [menu, setMenu] = useState<ChatMessage | null>(null);
  const [reporting, setReporting] = useState<ChatMessage | null>(null);
  const [people, setPeople] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const { data: room, isPending, error } = useQuery({
    queryKey: chatKeys.room(id),
    queryFn: () => api<ChatRoom>(`/events/${id}/chat`),
    refetchInterval: 60_000, // safety net; live updates come from the stream
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: chatKeys.room(id) });
    qc.invalidateQueries({ queryKey: chatKeys.mine });
  };
  const fail = (e: unknown) => toast({ tone: "error", title: "That didn't work", body: (e as Error).message });

  const send = useMutation({
    mutationFn: () => api<ChatMessage>(`/events/${id}/chat`, { method: "POST", body: { body: text.trim(), announcement: announce } }),
    onSuccess: (msg) => {
      qc.setQueryData<ChatRoom>(chatKeys.room(id), (r) => (r ? { ...r, messages: [...r.messages, msg] } : r));
      setText("");
      setAnnounce(false);
      refresh();
    },
    onError: (e) => toast({ tone: "warning", title: "Not sent", body: (e as Error).message }),
  });
  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: refresh,
    onError: fail,
  });

  // Mark read on open (the GET does it) and keep the unread badges in step.
  useEffect(() => {
    if (room) qc.invalidateQueries({ queryKey: chatKeys.mine });
  }, [room?.messages.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const count = room?.messages.length ?? 0;
  useLayoutEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [count]);

  if (isPending) return <div className="mx-auto max-w-2xl" aria-busy="true"><div className="skeleton h-64 rounded-[22px]" /></div>;
  if (error || !room) {
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <div className="card mx-auto mt-8 max-w-md p-8 text-center">
        <p className="headline">{missing ? "This chat is for the host and people going." : "Couldn't load the chat."}</p>
        <p className="callout mt-1 text-text-2">{missing ? "Register for the event to join its group chat." : "Check your connection, then try again."}</p>
        <Link to={`/event/${id}`} className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Back to the event</Link>
      </div>
    );
  }

  const host = room.role === "host";
  const back = () => navigate(host ? `/organizer/event/${id}` : `/event/${id}`);
  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    if (text.trim() && !send.isPending) send.mutate();
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col pb-40">
      <button onClick={back} className="pressable -ml-2 mb-2 inline-flex min-h-11 items-center gap-1 self-start rounded-full px-2 callout font-medium text-accent">
        <ArrowLeft className="size-5" aria-hidden /> {host ? "Event" : "Back"}
      </button>
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="title-2 truncate">{room.event.title}</h1>
          <p className="footnote mt-0.5 text-text-2 tnum">
            Group chat · {room.members === 1 ? "1 person" : `${room.members} people`} · {formatDayTime(room.event.start_at, room.event.start_at).split(",")[0]}
          </p>
        </div>
        {host && (
          <div className="flex shrink-0 gap-1">
            <Button size="sm" variant="quiet" aria-label="People in this chat" onClick={() => setPeople(true)}><Users className="size-5" aria-hidden /></Button>
            <Button size="sm" variant="quiet" aria-label={room.locked ? "Let everyone post" : "Only I can post"} disabled={room.read_only}
              onClick={() => act.mutate(() => api(`/events/${id}/chat/lock`, { method: "POST", body: { locked: !room.locked } }))}>
              {room.locked ? <Lock className="size-5" aria-hidden /> : <Unlock className="size-5" aria-hidden />}
            </Button>
          </div>
        )}
      </header>

      {room.pinned && (
        <div className="card mt-4 flex items-start gap-3 p-4">
          <Pin className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
          <div className="min-w-0">
            <p className="footnote font-semibold text-text-2">Pinned by the host</p>
            <p className="callout mt-0.5 whitespace-pre-wrap break-words">{room.pinned.body}</p>
          </div>
        </div>
      )}

      <ol className="mt-4 flex flex-col gap-2" aria-live="polite">
        {room.messages.length === 0 && (
          <li className="callout py-10 text-center text-text-2">
            {host ? "Say hello, share what to bring, or post updates here." : "No messages yet. Ask a question or say hi."}
          </li>
        )}
        {room.messages.map((m, i) => (
          <Bubble key={m.id} m={m} grouped={i > 0 && room.messages[i - 1].sender.id === m.sender.id} onMore={() => setMenu(m)} />
        ))}
      </ol>
      <div ref={bottom} />

      <div className="glass safe-bottom fixed inset-x-0 bottom-0 z-30 border-t border-line px-4 py-3">
        <div className="mx-auto max-w-2xl">
          {room.can_post ? (
            <form onSubmit={onSubmit} className="flex items-end gap-2">
              {host && (
                <button type="button" onClick={() => setAnnounce((v) => !v)} aria-pressed={announce}
                  aria-label="Send as announcement (also alerts everyone)"
                  className={`pressable grid size-11 shrink-0 place-items-center rounded-full ${announce ? "bg-accent-fill text-white" : "bg-accent-soft text-accent"}`}>
                  <Megaphone className="size-5" aria-hidden />
                </button>
              )}
              <label className="sr-only" htmlFor="chat-input">Message</label>
              <textarea id="chat-input" value={text} onChange={(e) => setText(e.target.value)} rows={1} maxLength={1000}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) onSubmit(e); }}
                placeholder={announce ? "Announcement to everyone" : "Message"}
                className="max-h-32 min-h-11 flex-1 resize-none rounded-[22px] bg-surface px-4 py-2.5 body outline-none ring-1 ring-line focus:ring-2 focus:ring-accent" />
              <Button type="submit" size="sm" aria-label="Send" loading={send.isPending} disabled={!text.trim()} className="size-11 shrink-0 !px-0">
                <Send className="size-5" aria-hidden />
              </Button>
            </form>
          ) : (
            <p className="callout py-2 text-center text-text-2">
              {room.read_only ? "This chat is closed now that the event is over." : "Only the host can post right now."}
            </p>
          )}
          {room.can_post && <p className="text-[12px] leading-4 mt-1.5 text-center text-text-2">Be kind. No payment requests or phone numbers. The host can remove messages.</p>}
        </div>
      </div>

      <Sheet open={!!menu} onClose={() => setMenu(null)} title="Message">
        {menu && (
          <div className="flex flex-col gap-2 pb-2">
            {host && !menu.hidden && (
              <Button variant="secondary" full onClick={() => { act.mutate(() => api(`/chat/messages/${menu.id}/pin?pinned=${!menu.pinned}`, { method: "POST" })); setMenu(null); }}>
                <Pin className="size-4" aria-hidden /> {menu.pinned ? "Unpin" : "Pin to top"}
              </Button>
            )}
            {(host || menu.sender.is_me) && !menu.hidden && (
              <Button variant="danger" full onClick={() => { act.mutate(() => api(`/chat/messages/${menu.id}`, { method: "DELETE" })); setMenu(null); }}>
                <Trash2 className="size-4" aria-hidden /> Remove message
              </Button>
            )}
            {!menu.sender.is_me && !menu.hidden && (
              <Button variant="quiet" full onClick={() => { setReporting(menu); setMenu(null); }}>
                <Flag className="size-4" aria-hidden /> Report
              </Button>
            )}
          </div>
        )}
      </Sheet>

      <Sheet open={!!reporting} onClose={() => setReporting(null)} title="Report message">
        <p className="callout text-text-2">ShowUp reviews reports. The sender isn't told who reported them.</p>
        <div className="mt-3 flex flex-col gap-2 pb-2">
          {REPORT_REASONS.map((r) => (
            <Button key={r} variant="secondary" full onClick={() => {
              const target = reporting;
              setReporting(null);
              if (target) api(`/chat/messages/${target.id}/report`, { method: "POST", body: { reason: r } })
                .then(() => toast({ tone: "success", title: "Thanks for reporting", body: "We'll take a look." }))
                .catch(fail);
            }}>{r}</Button>
          ))}
        </div>
      </Sheet>

      {host && <PeopleSheet open={people} onClose={() => setPeople(false)} eventId={id} onRemoved={refresh} />}
    </div>
  );
}

function Bubble({ m, grouped, onMore }: { m: ChatMessage; grouped: boolean; onMore: () => void }) {
  const mine = m.sender.is_me;
  return (
    <li className={`flex flex-col ${mine ? "items-end" : "items-start"} ${grouped ? "" : "mt-2"}`}>
      {!grouped && !mine && (
        <span className={`footnote mb-1 px-3 font-semibold ${m.sender.is_host ? "text-accent" : "text-text-2"}`}>
          {m.sender.name}{m.sender.is_host && " · Host"}
        </span>
      )}
      <div className={`group flex max-w-[85%] items-end gap-1 ${mine ? "flex-row-reverse" : ""}`}>
        <div className={`rounded-[20px] px-4 py-2.5 ${m.hidden ? "bg-transparent ring-1 ring-line" : m.announcement ? "bg-warning/15" : mine ? "bg-accent-fill text-white" : "bg-surface ring-1 ring-line"}`}>
          {m.hidden ? (
            <p className="callout italic text-text-2">Message removed</p>
          ) : (
            <>
              {m.announcement && <p className="text-[12px] leading-4 mb-0.5 flex items-center gap-1 font-semibold text-warning-text"><Megaphone className="size-3.5" aria-hidden />Announcement</p>}
              <p className="body whitespace-pre-wrap break-words">{m.body}</p>
            </>
          )}
          <p className={`text-[11px] leading-4 mt-0.5 tnum ${mine && !m.hidden && !m.announcement ? "text-white/75" : "text-text-2"}`}>{formatTime(m.created_at)}</p>
        </div>
        {!m.hidden && (
          <button onClick={onMore} aria-label="Message options" className="pressable grid size-11 shrink-0 place-items-center rounded-full text-text-2">
            <MoreHorizontal className="size-5" aria-hidden />
          </button>
        )}
      </div>
    </li>
  );
}

function PeopleSheet({ open, onClose, eventId, onRemoved }: { open: boolean; onClose: () => void; eventId: string; onRemoved: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data } = useQuery({
    queryKey: ["chat-members", eventId],
    queryFn: () => api<{ items: { id: string; name: string }[] }>(`/events/${eventId}/chat/members`),
    enabled: open,
  });
  const remove = useMutation({
    mutationFn: (uid: string) => api(`/events/${eventId}/chat/remove/${uid}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat-members", eventId] });
      onRemoved();
      toast({ tone: "success", title: "Removed from the chat", body: "They're still registered for the event." });
    },
    onError: (e) => toast({ tone: "error", title: "That didn't work", body: (e as Error).message }),
  });
  return (
    <Sheet open={open} onClose={onClose} title="People in this chat">
      {!data ? (
        <div className="skeleton h-24 rounded-[14px]" />
      ) : data.items.length === 0 ? (
        <p className="callout pb-2 text-text-2">No one has joined yet. Everyone who registers joins automatically.</p>
      ) : (
        <ul className="divide-y divide-line pb-2">
          {data.items.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 py-2">
              <span className="body">{p.name}</span>
              <Button size="sm" variant="quiet" onClick={() => remove.mutate(p.id)} aria-label={`Remove ${p.name} from the chat`}>
                <UserMinus className="size-4" aria-hidden /> Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}
