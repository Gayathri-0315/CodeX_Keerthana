import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";
import { api } from "./api";
import type { Area, EventDetail, FeedItem, FeedPage, FeedTab, Role, Slot, User } from "./types";

export const keys = {
  me: ["me"] as const,
  availability: ["availability"] as const,
  feedCount: ["feed", "count"] as const,
  feed: (tab: FeedTab) => ["feed", "list", tab] as const,
  /** Everything that depends on the user's free time or profile. */
  feedAll: ["feed"] as const,
  event: (id: string) => ["event", id] as const,
  config: ["config"] as const,
};

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api<{ user: User | null }>("/auth/session").then((r) => r.user),
    staleTime: 60_000,
  });
}

export function usePublicConfig() {
  return useQuery({
    queryKey: keys.config,
    queryFn: () => api<{ demo_mode: boolean; ai_live: boolean }>("/auth/config"),
    staleTime: Infinity,
  });
}

/** Everything that depends on who is signed in or on their profile. */
function useResetUserData() {
  const qc = useQueryClient();
  return (user: User | null) => {
    qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" && q.queryKey[0] !== "config" });
    qc.setQueryData(keys.me, user);
  };
}

export function useSignIn() {
  const reset = useResetUserData();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => api<User>("/auth/login", { method: "POST", body }),
    onSuccess: reset,
  });
}

export function useDemoSignIn() {
  const reset = useResetUserData();
  return useMutation({
    mutationFn: (role: Role) => api<User>("/auth/demo", { method: "POST", body: { role } }),
    onSuccess: reset,
  });
}

export function useRegister() {
  const reset = useResetUserData();
  return useMutation({
    mutationFn: (body: { name: string; email: string; password: string }) => api<User>("/auth/register", { method: "POST", body }),
    onSuccess: reset,
  });
}

export function useSignOut() {
  const reset = useResetUserData();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSuccess: () => reset(null),
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<User>) => api<User>("/users/me", { method: "PATCH", body: patch }),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: keys.me });
      const prev = qc.getQueryData<User | null>(keys.me);
      if (prev) qc.setQueryData(keys.me, { ...prev, ...patch });
      return { prev };
    },
    onError: (_e, _p, ctx) => ctx?.prev && qc.setQueryData(keys.me, ctx.prev),
    onSuccess: (user) => {
      qc.setQueryData(keys.me, user);
      qc.invalidateQueries({ queryKey: keys.feedAll });
    },
  });
}

export function useUpdateInterests() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { interests: { tag: string; weight: number }[]; interest_text?: string }) =>
      api<User>("/users/me/interests", { method: "PUT", body }),
    onSuccess: (user) => {
      qc.setQueryData(keys.me, user);
      qc.invalidateQueries({ queryKey: keys.feedAll });
    },
  });
}

export function useAvailability() {
  return useQuery({
    queryKey: keys.availability,
    queryFn: () => api<{ slots: Slot[] }>("/availability").then((r) => r.slots),
    staleTime: 30_000,
  });
}

export function useFeedCount() {
  return useQuery({
    queryKey: keys.feedCount,
    queryFn: () => api<{ fits: number; almost: number }>("/feed/count"),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useFeed(tab: FeedTab) {
  return useInfiniteQuery({
    queryKey: keys.feed(tab),
    queryFn: ({ pageParam }) => api<FeedPage>(`/feed?tab=${tab}&limit=20${pageParam ? `&cursor=${pageParam}` : ""}`),
    initialPageParam: "",
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: 30_000,
  });
}

const fetchEvent = (id: string) => api<EventDetail>(`/events/${id}`);

export function useEvent(id: string) {
  return useQuery({ queryKey: keys.event(id), queryFn: () => fetchEvent(id), staleTime: 30_000 });
}

/** Warm the detail cache and the page chunk on hover or touch start. */
export function usePrefetchEvent() {
  const qc = useQueryClient();
  return (id: string) => {
    void import("../pages/EventPage");
    void qc.prefetchQuery({ queryKey: keys.event(id), queryFn: () => fetchEvent(id), staleTime: 30_000 });
  };
}

type FeedCache = InfiniteData<FeedPage, string>;

/** Apply a change to an event wherever it is cached (every feed tab and its detail). */
function patchEventEverywhere(qc: QueryClient, id: string, fn: (e: FeedItem) => FeedItem | null) {
  qc.setQueriesData<FeedCache>({ queryKey: ["feed", "list"] }, (data) =>
    data && {
      ...data,
      pages: data.pages.map((p) => ({ ...p, items: p.items.map(fn).filter((e): e is FeedItem => e !== null) })),
    },
  );
  qc.setQueryData<EventDetail>(keys.event(id), (d) => (d ? ({ ...d, ...(fn(d) ?? { dismissed: true }) } as EventDetail) : d));
}

export function useSaveEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, saved }: { id: string; saved: boolean }) =>
      api<void>(`/events/${id}/save`, { method: saved ? "POST" : "DELETE" }),
    onMutate: async ({ id, saved }) => {
      await qc.cancelQueries({ queryKey: ["feed"] });
      const snapshot = qc.getQueriesData({ queryKey: ["feed"] });
      const detail = qc.getQueryData(keys.event(id));
      patchEventEverywhere(qc, id, (e) => (e.id === id ? { ...e, saved } : e));
      return { snapshot, detail };
    },
    onError: (_e, { id }, ctx) => {
      ctx?.snapshot.forEach(([key, data]) => qc.setQueryData(key, data));
      qc.setQueryData(keys.event(id), ctx?.detail);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.feed("saved") }),
  });
}

export function useDismissEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, undo }: { id: string; undo?: boolean }) =>
      api<void>(`/events/${id}/dismiss`, { method: undo ? "DELETE" : "POST" }),
    onMutate: async ({ id, undo }) => {
      await qc.cancelQueries({ queryKey: ["feed"] });
      const snapshot = qc.getQueriesData({ queryKey: ["feed"] });
      if (!undo) patchEventEverywhere(qc, id, (e) => (e.id === id ? null : e));
      return { snapshot };
    },
    onError: (_e, _v, ctx) => ctx?.snapshot.forEach(([key, data]) => qc.setQueryData(key, data)),
    onSettled: () => qc.invalidateQueries({ queryKey: ["feed"] }),
  });
}

export function useAreas(q: string) {
  return useQuery({
    queryKey: ["areas", q],
    queryFn: () => api<{ areas: Area[] }>(`/areas?q=${encodeURIComponent(q)}`).then((r) => r.areas),
    staleTime: Infinity,
    placeholderData: (prev) => prev,
  });
}
