import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, Clock, Copy, Flag, Lock, Megaphone, Pin, Send, ShieldCheck, Sparkles, Trash2, Unlock, UserMinus, Users } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Sheet } from "../components/ui/Sheet";
import { useToast } from "../components/ui/Toaster";
import { api, ApiError } from "../lib/api";
import { chatDayLabel, chatKeys, nameHue, type ChatMessage, type ChatRoom } from "../lib/chat";
import { formatDayTime, formatTime } from "../lib/format";
import { GroupAvatar } from "./ChatsPage";

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
  const [summary, setSummary] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const { data: room, isPending, error } = useQuery({
    queryKey: chatKeys.room(id),
    queryFn: () => api<ChatRoom>(`/events/${id}/chat`),
    refetchInterval: 60_000, // safety net; live updates come from the stream
  });
  // My messages still being checked and saved: shown at once with a clock, like a messaging app.
  const [outbox, setOutbox] = useState<ChatMessage[]>([]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: chatKeys.room(id) });
    qc.invalidateQueries({ queryKey: chatKeys.mine });
  };
  const fail = (e: unknown) => toast({ tone: "error", title: "That didn't work", body: (e as Error).message });

  // Sent messages show at once with a clock, like a messaging app; the server's checks run behind it.
  const send = useMutation({
    mutationFn: (v: { body: string; announcement: boolean; tempId: string }) =>
      api<ChatMessage>(`/events/${id}/chat`, { method: "POST", body: { body: v.body, announcement: v.announcement } }),
    onMutate: (v) => {
      const r = qc.getQueryData<ChatRoom>(chatKeys.room(id));
      setOutbox((o) => [...o, {
        id: v.tempId, body: v.body, hidden: false, announcement: v.announcement, pinned: false, created_at: new Date().toISOString(),
        sender: { id: "me", name: "You", is_host: r?.role === "host", is_me: true }, pending: true,
      }]);
      setText("");
      setAnnounce(false);
    },
    onSuccess: (msg, v) => {
      qc.setQueryData<ChatRoom>(chatKeys.room(id), (r) => (r && !r.messages.some((m) => m.id === msg.id) ? { ...r, messages: [...r.messages, msg] } : r));
      setOutbox((o) => o.filter((m) => m.id !== v.tempId));
      qc.invalidateQueries({ queryKey: chatKeys.mine });
    },
    onError: (e, v) => {
      setOutbox((o) => o.filter((m) => m.id !== v.tempId));
      setText((t) => t || v.body);
      setAnnounce(v.announcement);
      toast({ tone: "warning", title: "Not sent", body: (e as Error).message });
    },
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

  // Like a messaging app: open at the newest message, and follow new ones.
  const count = (room?.messages.length ?? 0) + outbox.length;
  useLayoutEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [count]);

  // The message box grows with the text, up to a few lines.
  useLayoutEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
  }, [text]);

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
  const messages = [...room.messages, ...outbox];
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate("/chats"));
  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    if (text.trim()) send.mutate({ body: text.trim(), announcement: announce, tempId: `tmp-${Date.now()}` });
    input.current?.focus();
  };

  return (
    <div className="-mx-4 -mt-4 flex min-h-[calc(100dvh-16px)] flex-col sm:mx-auto sm:mt-0 sm:max-w-2xl md:-mt-8 md:min-h-[calc(100dvh-56px)]">
      {/* Header: back, group photo, name and people, host tools */}
      <header className="glass safe-top sticky top-0 z-20 flex items-center gap-1 border-b border-line px-1 py-1.5 md:top-14 sm:rounded-t-[22px]">
        <button onClick={back} aria-label="Back" className="pressable grid size-11 shrink-0 place-items-center rounded-full text-accent">
          <ArrowLeft className="size-6" aria-hidden />
        </button>
        <Link to={host ? `/organizer/event/${id}` : `/event/${id}`} className="pressable flex min-w-0 flex-1 items-center gap-3 rounded-[14px] py-1 pr-2">
          <GroupAvatar title={room.event.title} poster={room.event.poster_url} id={room.event.id} size="size-10" />
          <span className="min-w-0">
            <span className="headline block truncate">{room.event.title}</span>
            <span className="footnote block truncate text-text-2 tnum">
              {room.read_only ? "Closed · " : room.locked ? "Only the host can post · " : ""}
              {room.members === 1 ? "1 participant" : `${room.members} participants`} · {formatDayTime(room.event.start_at, room.event.start_at).split(",")[0]}
            </span>
          </span>
        </Link>
        {host && (
          <div className="flex shrink-0">
            <IconButton label="Summary of the last day" onClick={() => setSummary(true)}><Sparkles className="size-5" aria-hidden /></IconButton>
            <IconButton label="Participants" onClick={() => setPeople(true)}><Users className="size-5" aria-hidden /></IconButton>
            <IconButton label={room.locked ? "Let everyone post" : "Only I can post"} disabled={room.read_only}
              onClick={() => act.mutate(() => api(`/events/${id}/chat/lock`, { method: "POST", body: { locked: !room.locked } }))}>
              {room.locked ? <Lock className="size-5" aria-hidden /> : <Unlock className="size-5" aria-hidden />}
            </IconButton>
          </div>
        )}
      </header>

      {room.pinned && (
        <button onClick={() => document.getElementById(`msg-${room.pinned!.id}`)?.scrollIntoView({ block: "center", behavior: "smooth" })}
          className="glass sticky top-[60px] z-10 flex items-center gap-3 border-b border-line px-4 py-2 text-left md:top-[116px]">
          <Pin className="size-4 shrink-0 text-accent" aria-hidden />
          <span className="min-w-0">
            <span className="footnote block font-semibold text-accent">Pinned message</span>
            <span className="callout block truncate">{room.pinned.body}</span>
          </span>
        </button>
      )}

      {/* Messages */}
      <div className="chat-wall flex-1 px-3 pb-4 pt-3 sm:px-4">
        <p className="mx-auto mb-3 max-w-[340px] rounded-[10px] bg-surface/80 px-3 py-1.5 text-center text-[12px] leading-4 text-text-2 shadow-[0_0_0_1px_var(--line)]">
          <ShieldCheck className="mr-1 inline size-3.5 align-[-2px]" aria-hidden />
          Only the host and people going can see this group. First names only; phone numbers and payment requests are blocked.
        </p>
        {messages.length === 0 ? (
          <p className="callout py-12 text-center text-text-2">
            {host ? "Say hello, share what to bring, or post updates here." : "No messages yet. Ask a question or say hi 👋"}
          </p>
        ) : (
          <ol className="flex flex-col" aria-live="polite" aria-label="Messages">
            {messages.map((m, i) => {
              const prev = messages[i - 1];
              const newDay = !prev || new Date(prev.created_at).toDateString() !== new Date(m.created_at).toDateString();
              const first = newDay || prev.sender.id !== m.sender.id || prev.announcement !== m.announcement;
              return (
                <li key={m.id} id={`msg-${m.id}`}>
                  {newDay && (
                    <div className="my-3 flex justify-center">
                      <span className="rounded-[8px] bg-surface px-3 py-1 text-[12px] font-medium text-text-2 shadow-[0_0_0_1px_var(--line)]">{chatDayLabel(m.created_at)}</span>
                    </div>
                  )}
                  <Bubble m={m} first={first} onOpen={() => setMenu(m)} />
                </li>
              );
            })}
          </ol>
        )}
        <div ref={bottom} />
      </div>

      {/* Message bar */}
      <div className="glass safe-bottom sticky bottom-0 z-20 border-t border-line px-2 py-2 sm:rounded-b-[22px]">
        {room.can_post ? (
          <form onSubmit={onSubmit} className="flex items-end gap-2">
            {host && (
              <button type="button" onClick={() => setAnnounce((v) => !v)} aria-pressed={announce}
                aria-label="Send as announcement (also alerts everyone)"
                className={`pressable grid size-11 shrink-0 place-items-center rounded-full ${announce ? "bg-warning text-white" : "text-text-2 hover:bg-text/6"}`}>
                <Megaphone className="size-5" aria-hidden />
              </button>
            )}
            <label className="sr-only" htmlFor="chat-input">Message</label>
            <textarea ref={input} id="chat-input" value={text} onChange={(e) => setText(e.target.value)} rows={1} maxLength={1000}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) onSubmit(e); }}
              placeholder={announce ? "Announcement to everyone" : "Message"}
              className="no-scrollbar max-h-32 min-h-11 flex-1 resize-none rounded-[22px] bg-surface px-4 py-[11px] body leading-[22px] outline-none shadow-[inset_0_0_0_1px_var(--line)] focus:shadow-[inset_0_0_0_2px_var(--accent)]" />
            <button type="submit" aria-label="Send" disabled={!text.trim()}
              className="pressable grid size-11 shrink-0 place-items-center rounded-full bg-accent-fill text-white transition-opacity disabled:opacity-40">
              <Send className="size-5" aria-hidden />
            </button>
          </form>
        ) : (
          <p className="callout py-2.5 text-center text-text-2">
            {room.read_only ? "This chat is closed now that the event is over." : "Only the host can send messages right now."}
          </p>
        )}
      </div>

      <Sheet open={!!menu} onClose={() => setMenu(null)} title="Message">
        {menu && (
          <div className="flex flex-col gap-2 pb-2">
            {menu.body && (
              <Button variant="secondary" full onClick={() => { void navigator.clipboard?.writeText(menu.body ?? ""); toast({ tone: "success", title: "Copied" }); setMenu(null); }}>
                <Copy className="size-4" aria-hidden /> Copy
              </Button>
            )}
            {host && !menu.hidden && (
              <Button variant="secondary" full onClick={() => { act.mutate(() => api(`/chat/messages/${menu.id}/pin?pinned=${!menu.pinned}`, { method: "POST" })); setMenu(null); }}>
                <Pin className="size-4" aria-hidden /> {menu.pinned ? "Unpin" : "Pin to top"}
              </Button>
            )}
            {(host || menu.sender.is_me) && !menu.hidden && (
              <Button variant="danger" full onClick={() => { act.mutate(() => api(`/chat/messages/${menu.id}`, { method: "DELETE" })); setMenu(null); }}>
                <Trash2 className="size-4" aria-hidden /> Delete for everyone
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

      {host && <SummarySheet open={summary} onClose={() => setSummary(false)} eventId={id} />}
      {host && <PeopleSheet open={people} onClose={() => setPeople(false)} eventId={id} onRemoved={refresh} />}
    </div>
  );
}

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button onClick={onClick} disabled={disabled} aria-label={label} title={label}
      className="pressable grid size-11 place-items-center rounded-full text-accent hover:bg-text/6 disabled:opacity-40">
      {children}
    </button>
  );
}

/** One message, messaging-app style: mine on the right, others on the left with their name in their colour. Tap for options. */
function Bubble({ m, first, onOpen }: { m: ChatMessage; first: boolean; onOpen: () => void }) {
  const mine = m.sender.is_me;
  const tail = first ? (mine ? "rounded-tr-[6px]" : "rounded-tl-[6px]") : "";
  const tone = m.hidden
    ? "bg-surface/70 text-text-2 shadow-[0_0_0_1px_var(--line)]"
    : m.announcement
      ? "bg-warning/15 shadow-[0_0_0_1px_color-mix(in_srgb,var(--warning)_35%,transparent)]"
      : mine
        ? "bg-accent-fill text-white"
        : "bg-surface shadow-[0_1px_0_var(--line)]";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"} ${first ? "mt-2" : "mt-0.5"}`}>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !m.pending && onOpen()}
        onKeyDown={(e) => !m.pending && (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen())}
        aria-label={`${mine ? "You" : m.sender.name}: ${m.hidden ? "message removed" : m.body}. Options`}
        className={`max-w-[82%] cursor-pointer select-text rounded-[18px] px-3 pb-1.5 pt-1.5 sm:max-w-[70%] ${tone} ${tail}`}
      >
        {first && !mine && !m.hidden && (
          <p className="chat-name text-[13px] font-semibold leading-5" style={{ "--h": nameHue(m.sender.id) } as CSSProperties}>
            {m.sender.name}{m.sender.is_host && <span className="ml-1.5 rounded-[6px] bg-accent-soft px-1.5 py-px text-[11px] font-semibold text-accent">Host</span>}
          </p>
        )}
        {m.announcement && !m.hidden && (
          <p className="flex items-center gap-1 text-[12px] font-semibold leading-5 text-warning-text"><Megaphone className="size-3.5" aria-hidden />Announcement</p>
        )}
        <p className="body whitespace-pre-wrap break-words">
          {m.hidden ? <span className="italic"><Ban className="mr-1 inline size-4 align-[-3px]" aria-hidden />This message was deleted</span> : m.body}
          {/* Space for the time so it never overlaps the last line. */}
          <span className="inline-block w-[58px]" aria-hidden />
        </p>
        <p className={`-mt-4 text-right text-[11px] leading-4 tnum ${mine && !m.hidden && !m.announcement ? "text-white/75" : "text-text-2"}`}>
          {m.pinned && <Pin className="mr-1 inline size-3 align-[-1px]" aria-label="Pinned" />}
          {formatTime(m.created_at)}
          {m.pending && <Clock className="ml-1 inline size-3 align-[-1px]" aria-label="Sending" />}
        </p>
      </div>
    </div>
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

type Summary = { summary: string[]; questions: string[]; messages: number; source: "ai" | "rules" };

/** Host: what the chat talked about in the last day, and questions still waiting for a reply. */
function SummarySheet({ open, onClose, eventId }: { open: boolean; onClose: () => void; eventId: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["chat-summary", eventId],
    queryFn: () => api<Summary>(`/events/${eventId}/chat/summary`),
    enabled: open,
    staleTime: 60_000,
  });
  return (
    <Sheet open={open} onClose={onClose} title="Last 24 hours">
      <div className="pb-2">
        {isPending ? (
          <div className="flex flex-col gap-2" aria-busy="true"><div className="skeleton h-5 w-3/4 rounded" /><div className="skeleton h-5 w-1/2 rounded" /></div>
        ) : isError ? (
          <p className="callout text-danger-text">{(error as Error).message}</p>
        ) : data.messages === 0 ? (
          <p className="callout text-text-2">No messages from students in the last day.</p>
        ) : (
          <>
            <ul className="flex flex-col gap-1.5">
              {data.summary.map((s) => <li key={s} className="body">{s}</li>)}
            </ul>
            {data.questions.length > 0 && (
              <>
                <h3 className="headline mt-5">Waiting for your reply</h3>
                <ul className="mt-2 flex flex-col gap-2">
                  {data.questions.map((q) => <li key={q} className="callout rounded-[14px] bg-text/6 px-3.5 py-2.5">{q}</li>)}
                </ul>
              </>
            )}
          </>
        )}
      </div>
    </Sheet>
  );
}
