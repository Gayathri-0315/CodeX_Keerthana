import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { keys } from "./queries";
import type { Analytics, AppNotification, Invite, Registrant, Registration } from "./types";

export const attKeys = {
  mine: ["registrations", "me"] as const,
  notifications: ["notifications"] as const,
  registrants: (id: string) => ["org", "registrants", id] as const,
  analytics: (id: string) => ["org", "analytics", id] as const,
};

/** A registration change touches the feed, the event, My events and seat counts. */
export function refreshAfterSeatChange(qc: QueryClient, eventId?: string) {
  qc.invalidateQueries({ queryKey: keys.feedAll });
  qc.invalidateQueries({ queryKey: attKeys.mine });
  qc.invalidateQueries({ queryKey: attKeys.notifications });
  if (eventId) qc.invalidateQueries({ queryKey: keys.event(eventId) });
}

export function useMyRegistrations() {
  return useQuery({
    queryKey: attKeys.mine,
    queryFn: () => api<{ upcoming: Registration[]; waitlist: Registration[]; past: Registration[] }>("/registrations/me"),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, external }: { eventId: string; external?: boolean }) =>
      api<Registration>(`/events/${eventId}/register`, { method: "POST", body: { external: !!external } }),
    onSuccess: (r) => refreshAfterSeatChange(qc, r.event.id),
  });
}

export function useCancelRegistration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Registration>(`/registrations/${id}/cancel`, { method: "POST" }),
    onSuccess: (r) => refreshAfterSeatChange(qc, r.event.id),
  });
}

export function useConfirmSeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Registration>(`/registrations/${id}/confirm-seat`, { method: "POST" }),
    onSuccess: (r) => refreshAfterSeatChange(qc, r.event.id),
  });
}

export function useConfirmReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Registration>(`/registrations/${id}/confirm-reminder`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: attKeys.mine }),
  });
}

export function useFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: "as_described" | "not_as_described" }) =>
      api<void>(`/registrations/${id}/feedback`, { method: "POST", body: { kind } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: attKeys.mine }),
  });
}

// ---- go together ----

export function useCreateInvite() {
  return useMutation({
    mutationFn: (registrationId: string) => api<{ code: string; url: string }>(`/registrations/${registrationId}/invite`, { method: "POST" }),
  });
}

export function useInvite(code: string) {
  return useQuery({ queryKey: ["invite", code], queryFn: () => api<Invite>(`/invites/${code}`), retry: false });
}

export function useAcceptInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api<Registration>(`/invites/${code}/accept`, { method: "POST" }),
    onSuccess: (r) => refreshAfterSeatChange(qc, r.event.id),
  });
}

/** Where to go after signing in, when someone arrived through an invite link. */
const RETURN_KEY = "showup-return-to";
export const returnTo = {
  set(path: string) {
    try {
      sessionStorage.setItem(RETURN_KEY, path);
    } catch {
      /* storage blocked: they'll land on Home instead */
    }
  },
  take(): string | null {
    try {
      const p = sessionStorage.getItem(RETURN_KEY);
      sessionStorage.removeItem(RETURN_KEY);
      return p;
    } catch {
      return null;
    }
  },
};

// ---- notifications ----

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: attKeys.notifications,
    queryFn: () => api<{ items: AppNotification[]; unread: number }>("/notifications"),
    enabled,
    staleTime: 30_000,
  });
}

export function useNotificationAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind }: { id?: string; kind: "read" | "click" | "dismiss" | "read_all" }) =>
      kind === "read_all"
        ? api<void>("/notifications/read-all", { method: "POST" })
        : api<void>(`/notifications/${id}/${kind === "dismiss" ? "dismiss" : `read${kind === "click" ? "?clicked=true" : ""}`}`, { method: "POST" }),
    onMutate: async ({ id, kind }) => {
      await qc.cancelQueries({ queryKey: attKeys.notifications });
      const prev = qc.getQueryData<{ items: AppNotification[]; unread: number }>(attKeys.notifications);
      if (prev) {
        const now = new Date().toISOString();
        const items =
          kind === "dismiss"
            ? prev.items.filter((n) => n.id !== id)
            : prev.items.map((n) => (kind === "read_all" || n.id === id ? { ...n, read_at: n.read_at ?? now } : n));
        qc.setQueryData(attKeys.notifications, { items, unread: items.filter((n) => !n.read_at).length });
      }
      return { prev };
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(attKeys.notifications, ctx.prev),
  });
}

// ---- organizer ----

export function useRegistrants(eventId: string) {
  return useQuery({
    queryKey: attKeys.registrants(eventId),
    queryFn: () => api<{ registrations: Registrant[] }>(`/organizer/events/${eventId}/registrations`).then((r) => r.registrations),
  });
}

export function useAnalytics(eventId: string) {
  return useQuery({ queryKey: attKeys.analytics(eventId), queryFn: () => api<Analytics>(`/organizer/events/${eventId}/analytics`) });
}

export type CheckinResult = { name: string; status: "checked_in" | "already"; checked_in_at: string; count: number };

export function useCheckin(eventId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => api<CheckinResult>(`/organizer/events/${eventId}/checkin`, { method: "POST", body: { token } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: attKeys.analytics(eventId) });
      qc.invalidateQueries({ queryKey: attKeys.registrants(eventId) });
    },
  });
}

export function useMessageRegistrants(eventId: string) {
  return useMutation({
    mutationFn: (text: string) => api<{ sent: number }>(`/organizer/events/${eventId}/message`, { method: "POST", body: { text } }),
  });
}

export function useCancelEvent(eventId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ notified: number }>(`/organizer/events/${eventId}/cancel`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org"] }),
  });
}

/** "Starts in 2d 5h" style countdown text. */
export function countdown(iso: string, now = Date.now()): string {
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return "Started";
  const m = Math.floor(ms / 60_000);
  const d = Math.floor(m / 1440);
  const h = Math.floor((m % 1440) / 60);
  if (d > 0) return `Starts in ${d}d ${h}h`;
  if (h > 0) return `Starts in ${h}h ${m % 60}m`;
  return `Starts in ${m} min`;
}

export function mmss(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((new Date(iso).getTime() - now) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
