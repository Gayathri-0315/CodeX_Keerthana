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
};

export type ChatRoom = {
  event: { id: string; title: string; start_at: string };
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

/** Chats I'm in, with unread counts. Refreshed live by the "chat" stream event. */
export function useMyChats(enabled = true) {
  return useQuery({
    queryKey: chatKeys.mine,
    queryFn: () => api<{ items: { event_id: string; unread: number }[] }>("/me/chats"),
    enabled,
    staleTime: 30_000,
  });
}

export function useChatEntry(eventId: string, enabled: boolean) {
  const { data } = useMyChats(enabled);
  const item = data?.items.find((i) => i.event_id === eventId);
  return { inChat: !!item, unread: item?.unread ?? 0 };
}
