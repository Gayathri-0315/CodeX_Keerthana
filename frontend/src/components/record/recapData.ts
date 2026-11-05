import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";

type Cat = { slug: string; name: string; emoji: string; count: number };
export type Recap = {
  period: string;
  period_label: string;
  first_name: string;
  college: string | null;
  events_attended: number;
  hours: number;
  categories: Cat[];
  top_categories: Cat[];
  topics: number;
  longest_streak_weeks: number;
  busiest_month: { month: string; count: number } | null;
  weekend_pct: number;
  evening_pct: number;
  morning_pct: number;
  style: { label: string; line: string; reason: string };
  short: boolean;
};

export function periodOf(d = new Date()): string {
  return `${d.getFullYear()}-H${d.getMonth() < 6 ? 1 : 2}`;
}

export function useRecap(period: string) {
  return useQuery({ queryKey: ["registrations", "me", "recap", period], queryFn: () => api<Recap>(`/me/recap?period=${period}`), staleTime: 60_000 });
}

