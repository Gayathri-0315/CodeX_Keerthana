export type Role = "student" | "organizer" | "admin";

export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  city: string;
  home_area: string | null;
  home_lat: number | null;
  home_lng: number | null;
  max_distance_km: number;
  budget_max_inr: number | null;
  format_pref: "in_person" | "online" | "either";
  skill_level: "beginner" | "intermediate" | "advanced";
  eligibility_tags: string[];
  interest_text: string;
  interests: { tag: string; weight: number }[];
  strict_schedule: boolean;
  show_almost: boolean;
  telegram_linked: boolean;
  notif_channels: { in_app?: boolean; telegram?: boolean; email?: boolean };
  notif_max_per_week: number;
  quiet_hours_start: string;
  quiet_hours_end: string;
  notif_paused_until: string | null;
  onboarded: boolean;
  organizer: { id: string; org_name: string; trust_level: string } | null;
};

export type Slot = {
  day_of_week: number;
  start_min: number;
  end_min: number;
  recurring: boolean;
  date: string | null;
  kind: "free" | "busy_override";
  source: "manual" | "timetable";
};

export type EventSummary = {
  id: string;
  title: string;
  category: string;
  tags: string[];
  mode: "in_person" | "online" | "hybrid";
  venue_name: string | null;
  start_at: string;
  end_at: string;
  fee_inr: number;
  verification_label: "organizer_verified" | "details_reviewed" | "unverified";
  organizer_name: string | null;
  fits: boolean;
  almost: boolean;
  reason: string | null;
  distance_km: number | null;
  waitlist: boolean;
};

export type Area = { name: string; lat: number; lng: number };
