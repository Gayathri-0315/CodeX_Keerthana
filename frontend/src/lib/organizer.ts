import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { EventForm, Extraction, OrgEvent, OrgSummary, Preview, ReviewItem } from "./types";

export const orgKeys = {
  summary: ["org", "summary"] as const,
  events: ["org", "events"] as const,
  event: (id: string) => ["org", "event", id] as const,
  samples: ["org", "samples"] as const,
  queue: ["admin", "queue"] as const,
};

export function useOrgSummary() {
  return useQuery({ queryKey: orgKeys.summary, queryFn: () => api<OrgSummary>("/organizer/summary") });
}

export function useOrgEvents() {
  return useQuery({ queryKey: orgKeys.events, queryFn: () => api<{ events: OrgEvent[] }>("/organizer/events").then((r) => r.events) });
}

export function useOrgEvent(id: string | undefined) {
  return useQuery({ queryKey: orgKeys.event(id ?? ""), queryFn: () => api<OrgEvent>(`/organizer/events/${id}`), enabled: !!id });
}

export function useSamplePosters() {
  return useQuery({
    queryKey: orgKeys.samples,
    queryFn: () => api<{ posters: { name: string; title: string; url: string }[] }>("/organizer/samples").then((r) => r.posters),
    staleTime: Infinity,
  });
}

export function useExtractPoster() {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<Extraction>("/organizer/events/extract", { form });
    },
  });
}

export function previewEvent(form: EventForm, signal: AbortSignal) {
  return api<Preview>("/organizer/events/preview", { method: "POST", body: form, signal });
}

/** Save (create or update) then publish, in one action. */
export function usePublishEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, form }: { id: string | null; form: EventForm }) => {
      const saved = await api<OrgEvent>(`/organizer/events${id ? `?event_id=${id}` : ""}`, { method: "POST", body: form });
      if (saved.status === "published") return { ...saved, message: "Changes saved. Your event is live." };
      return api<OrgEvent>(`/organizer/events/${saved.id}/publish`, { method: "POST" });
    },
    onSuccess: (event) => {
      qc.setQueryData(orgKeys.event(event.id), event);
      qc.invalidateQueries({ queryKey: ["org"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

export function useSaveDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, form }: { id: string | null; form: EventForm }) =>
      api<OrgEvent>(`/organizer/events${id ? `?event_id=${id}` : ""}`, { method: "POST", body: form }),
    onSuccess: (event) => {
      qc.setQueryData(orgKeys.event(event.id), event);
      qc.invalidateQueries({ queryKey: orgKeys.events });
    },
  });
}

export function useAppeal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) => api<OrgEvent>(`/organizer/events/${id}/appeal`, { method: "POST", body: { note } }),
    onSuccess: (event) => {
      qc.setQueryData(orgKeys.event(event.id), event);
      qc.invalidateQueries({ queryKey: ["org"] });
    },
  });
}

// ---- admin ----

export function useReviewQueue() {
  return useQuery({ queryKey: orgKeys.queue, queryFn: () => api<{ items: ReviewItem[] }>("/admin/review-queue").then((r) => r.items) });
}

export function useAdminAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, id }: { kind: "approve" | "reject" | "verify"; id: string }) =>
      api<unknown>(kind === "verify" ? `/admin/organizers/${id}/verify` : `/admin/events/${id}/${kind}`, { method: "POST" }),
    onSettled: () => qc.invalidateQueries({ queryKey: orgKeys.queue }),
  });
}

export function useReportEvent() {
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api<void>(`/events/${id}/report`, { method: "POST", body: { reason } }),
  });
}

export const STATUS_CHIP: Record<string, { text: string; tone: "neutral" | "accent" | "warning" | "success" }> = {
  draft: { text: "Draft", tone: "neutral" },
  pending_review: { text: "Pending review", tone: "warning" },
  published: { text: "Live", tone: "success" },
  blocked: { text: "Blocked", tone: "warning" },
  cancelled: { text: "Cancelled", tone: "neutral" },
};
