import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type ChatMessage = {
  id: string;
  body: string | null;
  hidden: boolean;
  announcement: boolean;
  pinned: boolean;
  created_at: string;
  sender: { id: string; name: string; is_host: boolean; is_me: boolean };
  /** Shown at once while the server checks and saves it. */
  pending?: boolean;
};

export type ChatRoom = {
  event: { id: string; title: string; start_at: string; poster_url: string | null };
  role: "host" | "member";
  locked: boolean;
  read_only: boolean;
  can_post: boolean;
  members: number;
  pinned: ChatMessage | null;
  messages: ChatMessage[];
};

export const chatKeys = {
  room: (id: string) => ["chat", id] as const,
  mine: ["chats"] as const,
};

export type ChatListItem = {
  event_id: string;
  title: string;
  poster_url: string | null;
  start_at: string;
  unread: number;
  read_only: boolean;
  last: { body: string | null; sender: string; announcement: boolean; at: string } | null;
};

/** Chats I'm in, newest activity first, with unread counts. Refreshed live by the "chat" stream event. */
export function useMyChats(enabled = true) {
  return useQuery({
    queryKey: chatKeys.mine,
    queryFn: () => api<{ items: ChatListItem[] }>("/me/chats"),
    enabled,
    staleTime: 30_000,
  });
}

export function useChatEntry(eventId: string, enabled: boolean) {
  const { data } = useMyChats(enabled);
  const item = data?.items.find((i) => i.event_id === eventId);
  return { inChat: !!item, unread: item?.unread ?? 0 };
}

const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

/** Chat list time: "10:42" today, "Yesterday", a weekday this week, else a short date. */
export function chatListTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  if (sameDay(d, now)) return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (sameDay(d, y)) return "Yesterday";
  if (now.getTime() - d.getTime() < 6 * 86_400_000) return d.toLocaleDateString([], { weekday: "long" });
  return d.toLocaleDateString([], { day: "numeric", month: "short" });
}

/** Date divider inside a chat: "Today", "Yesterday", or "Mon, 3 Nov". */
export function chatDayLabel(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  if (sameDay(d, now)) return "Today";
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (sameDay(d, y)) return "Yesterday";
  return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short", year: d.getFullYear() === now.getFullYear() ? undefined : "numeric" });
}

/** A steady colour per person, like group chat names. Used as hsl(hue ...). */
export function nameHue(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 360;
  return h;
}
