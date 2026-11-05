import { useQueryClient } from "@tanstack/react-query";
import { Bell, CalendarClock, Megaphone, MapPin, Sparkles, Ticket, TriangleAlert, Users } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { attKeys, refreshAfterSeatChange } from "../../lib/attendance";
import { chatKeys } from "../../lib/chat";
import { useMe } from "../../lib/queries";
import type { AppNotification, NotificationAction, Registration } from "../../lib/types";
import { useToast } from "../ui/Toaster";
import { showCheckinMoment } from "./CheckinMoment";

const ICON = {
  match: Sparkles,
  similar: Sparkles,
  deadline: CalendarClock,
  seat_opened: Ticket,
  reminder_leave_by: MapPin,
  cancelled_event: TriangleAlert,
  buddy_joined: Users,
  buddy_cancelled: Users,
  chat_announcement: Megaphone,
};

/** Listens on /api/stream and turns each alert into a Dynamic-Island toast with its actions. */
export function LiveAlerts() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const handlers = useRef({ toast, navigate });
  handlers.current = { toast, navigate };

  useEffect(() => {
    if (!me) return;
    const es = new EventSource("/api/stream");
    es.addEventListener("checked_in", (e) => {
      const d: { event_id: string; title: string } = JSON.parse((e as MessageEvent).data);
      refreshAfterSeatChange(qc, d.event_id);
      showCheckinMoment(d.title);
    });
    es.addEventListener("chat", (e) => {
      const d: { event_id: string } = JSON.parse((e as MessageEvent).data);
      qc.invalidateQueries({ queryKey: chatKeys.room(d.event_id) });
      qc.invalidateQueries({ queryKey: chatKeys.mine });
    });
    es.addEventListener("notification", (e) => {
      const n: AppNotification = JSON.parse((e as MessageEvent).data);
      qc.invalidateQueries({ queryKey: attKeys.notifications });
      if (["seat_opened", "cancelled_event", "buddy_joined", "buddy_cancelled"].includes(n.type)) refreshAfterSeatChange(qc, n.event_id ?? undefined);
      const { toast, navigate } = handlers.current;
      // Already looking at that chat: the message is on screen, no toast needed.
      if (n.type === "chat_announcement" && window.location.pathname === `/event/${n.event_id}/chat`) return;
      toast({
        title: n.title,
        body: n.body,
        tone: n.type === "seat_opened" || n.type === "cancelled_event" ? "warning" : n.type === "buddy_joined" ? "success" : "info",
        icon: ICON[n.type as keyof typeof ICON] ?? Bell,
        actions: n.actions.slice(0, 2).map((a) => ({ label: a.label, onClick: () => act(a, n) })),
      });

      function act(a: NotificationAction, note: AppNotification) {
        void api(`/notifications/${note.id}/read?clicked=true`, { method: "POST" }).catch(() => {});
        if (a.kind === "view" || a.kind === "register") return navigate(`/event/${a.event_id}`);
        if (a.kind === "url") return a.url.startsWith("/") ? navigate(a.url) : void window.open(a.url, "_blank", "noopener");
        if (a.kind === "feedback_up" || a.kind === "feedback_down") {
          return void api(`/registrations/${a.registration_id}/feedback`, { method: "POST", body: { kind: a.kind === "feedback_up" ? "as_described" : "not_as_described" } })
            .then(() =>
              toast({
                tone: "success",
                title: "Thanks",
                body: note.suggested ? `You might like ${note.suggested.title}.` : "That helps the next students choose.",
                action: note.suggested ? { label: "View", onClick: () => navigate(`/event/${note.suggested!.event_id}`) } : undefined,
              }),
            )
            .catch((err) => toast({ tone: "error", title: "That didn't work", body: (err as Error).message }));
        }
        if (a.kind === "cancel" || !("registration_id" in a)) return navigate(`/my`);
        const path = a.kind === "confirm_seat" ? "confirm-seat" : "confirm-reminder";
        api<Registration>(`/registrations/${a.registration_id}/${path}`, { method: "POST" })
          .then((r) => {
            refreshAfterSeatChange(qc, r.event.id);
            toast({ tone: "success", title: a.kind === "confirm_seat" ? "Seat confirmed" : "Great, see you there", body: r.event.title });
          })
          .catch((err) => toast({ tone: "error", title: "That didn't work", body: (err as Error).message }));
      }
    });
    return () => es.close();
  }, [me?.id, qc]); // reconnect only when the signed-in user changes

  return null;
}
