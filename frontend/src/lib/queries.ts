import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Area, EventSummary, Role, Slot, User } from "./types";

export const keys = {
  me: ["me"] as const,
  availability: ["availability"] as const,
  feedCount: ["feed", "count"] as const,
  events: ["events"] as const,
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
      qc.invalidateQueries({ queryKey: keys.feedCount });
      qc.invalidateQueries({ queryKey: keys.events });
    },
  });
}

export function useUpdateInterests() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { interests: { tag: string; weight: number }[]; interest_text?: string }) =>
      api<User>("/users/me/interests", { method: "PUT", body }),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
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

export function useEvents() {
  return useQuery({
    queryKey: keys.events,
    queryFn: () => api<{ events: EventSummary[] }>("/events").then((r) => r.events),
    staleTime: 30_000,
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
