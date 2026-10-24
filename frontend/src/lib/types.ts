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

export type FeedTab = "for_you" | "almost" | "saved";

export type FeedItem = {
  id: string;
  title: string;
  category: string;
  tags: string[];
  mode: "in_person" | "online" | "hybrid";
  venue_name: string | null;
  start_at: string;
  end_at: string;
  fee_inr: number;
  capacity: number | null;
  seats_taken: number;
  poster_url: string | null;
  verification_label: "organizer_verified" | "details_reviewed" | "unverified";
  organizer_name: string | null;
  distance_km: number | null;
  travel_min: number;
  fits: boolean;
  almost: boolean;
  clash: string | null;
  match: number | null;
  interest: number | null;
  reasons: string[];
  card_reasons: string[];
  waitlist: boolean;
  saved: boolean;
  dismissed: boolean;
};

export type FeedPage = { items: FeedItem[]; next_cursor: string | null; total: number };

export type EventDetail = FeedItem & {
  description: string;
  address: string | null;
  lat: number | null;
  lng: number | null;
  registration_deadline: string | null;
  registration_url: string | null;
  eligibility_text: string | null;
  skill_level: string | null;
  status: string;
  organizer: { name: string; trust_level: string; trust_label: string } | null;
  why_not: string | null;
  maps_url: string | null;
};

export type Area = { name: string; lat: number; lng: number };
