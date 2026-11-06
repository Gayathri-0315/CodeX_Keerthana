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
  max_distance_km: number | null; // null = anywhere
  budget_max_inr: number | null;
  format_pref: "in_person" | "online" | "either";
  skill_level: "beginner" | "intermediate" | "advanced";
  eligibility_tags: string[];
  interest_text: string;
  interests: { tag: string; weight: number }[];
  strict_schedule: boolean;
  show_almost: boolean;
  notif_channels: { in_app?: boolean; email?: boolean };
  notif_max_per_week: number;
  quiet_hours_start: string;
  quiet_hours_end: string;
  notif_paused_until: string | null;
  onboarded: boolean;
  follow_updates: boolean;
  college: string | null;
  organizer: { id: string; org_name: string; trust_level: string; college_or_company: string | null } | null;
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
export type HomeTab = FeedTab | "explore";
export type TimeFit = { fits: boolean; reason: string | null };

export type RegStatus = "registered" | "waitlisted" | "promoted_pending" | "cancelled" | "attended" | "no_show";

export type RegistrationBrief = {
  id: string;
  status: RegStatus;
  waitlist_position: number | null;
  promotion_expires_at: string | null;
  external: boolean;
};

export type Companion = { name: string; status: RegStatus };

export type Registration = RegistrationBrief & {
  companions: Companion[];
  checkin_token: string;
  checkin_code: string;
  checked_in_at: string | null;
  reminder_confirmed: boolean;
  leave_by: string | null;
  registered_at: string;
  feedback?: "as_described" | "not_as_described" | null;
  event: {
    id: string;
    title: string;
    category: string;
    poster_url: string | null;
    mode: FeedItem["mode"];
    venue_name: string | null;
    address: string | null;
    start_at: string;
    end_at: string;
    fee_inr: number;
    status: string;
    maps_url: string | null;
  };
  toast?: { title: string; body: string };
};

export type NotificationAction =
  | { label: string; kind: "view" | "register"; event_id: string }
  | { label: string; kind: "confirm_seat" | "confirm_reminder" | "cancel" | "feedback_up" | "feedback_down"; registration_id: string }
  | { label: string; kind: "url"; url: string };

export type AppNotification = {
  id: string;
  type: string;
  title: string;
  body: string;
  event_id: string | null;
  event_title: string | null;
  actions: NotificationAction[];
  created_at: string;
  read_at: string | null;
  suggested?: { event_id: string; title: string } | null;
};

export type Registrant = {
  id: string;
  name: string;
  status: RegStatus;
  waitlist_position: number | null;
  registered_at: string;
  checked_in_at: string | null;
  external: boolean;
  with_friends: boolean;
};

export type Invite = {
  code: string;
  inviter: string;
  going: number;
  problem: string | null;
  event: {
    id: string;
    title: string;
    category: string;
    poster_url: string | null;
    venue_name: string | null;
    mode: FeedItem["mode"];
    fee_inr: number;
    start_at: string | null;
    end_at: string | null;
  };
};

export type Analytics = {
  /** One plain, actionable sentence (totals only), or null. */
  advice: string | null;
  /** "learned" once enough past events beat the rules; "rules" until then. */
  estimate: "learned" | "rules";
  learned_from: number | null;
  registered: number;
  capacity: number | null;
  waitlisted: number;
  expected: number;
  expected_low: number;
  expected_high: number;
  actual: number;
  ended: boolean;
  described_pct: number | null;
  described_answers: number;
};

export type FeedItem = {
  id: string;
  registration: RegistrationBrief | null;
  classmates_going: { count: number; label: string } | null;
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
  fits: boolean | null; // null for guests and organizers
  almost: boolean;
  clash: string | null;
  match: number | null;
  interest: number | null;
  reasons: string[];
  card_reasons: string[];
  waitlist: boolean;
  saved: boolean;
  dismissed: boolean;
  time_fit?: TimeFit | null; // Explore only; null for internships (no session to fit)
  category_slug: string | null;
  guest?: boolean; // public card: no personal fit data
  event_type: EventType;
  organizer_slug?: string | null;
};

export type FeedPage = { items: FeedItem[]; next_cursor: string | null; total: number };

export type EventDetail = FeedItem & {
  description: string;
  /** Internships that take applications on ShowUp: mine, if I applied. */
  application?: { id: string; status: "submitted" | "shortlisted" | "declined"; at: string } | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  registration_deadline: string | null;
  registration_url: string | null;
  eligibility_text: string | null;
  skill_level: string | null;
  status: string;
  organizer: {
    name: string;
    slug: string | null;
    trust_level: string;
    trust_label: string;
    logo_url: string | null;
    bio: string | null;
    org_type: string | null;
    college_or_company: string | null;
    city: string | null;
    website: string | null;
    instagram: string | null;
    linkedin: string | null;
    contact_email: string | null;
  } | null;
  why_not: string | null;
  maps_url: string | null;
  next_waitlist_position?: number;
  companions: Companion[];
};

export type Area = { name: string; lat: number; lng: number };

// ---- organizer ----

export type EventType = "hackathon" | "competition" | "internship" | "workshop" | "conference" | "meetup" | "webinar" | "other";

export type EventForm = {
  title: string;
  description: string;
  category: string;
  event_type: EventType;
  category_slug: string | null;
  tags: string[];
  date: string | null;
  start_time: string | null;
  end_time: string | null;
  mode: "in_person" | "online" | "hybrid";
  venue_name: string | null;
  address: string | null;
  area: string | null;
  fee_inr: number;
  capacity: number | null;
  registration_deadline: string | null;
  eligibility_text: string | null;
  eligibility_tags: string[];
  skill_level: "beginner" | "intermediate" | "advanced" | null;
  registration_url: string | null;
  poster_url: string | null;
  source: "web_upload" | "form";
  field_confidence: Record<string, number | null>;
};

export type Risk = { score: number; level: "low" | "medium" | "high"; reasons: string[]; duplicate_of: string | null };
export type EventStatus = "draft" | "pending_review" | "published" | "blocked" | "cancelled";

export type OrgEvent = {
  id: string;
  status: EventStatus;
  verification_label: FeedItem["verification_label"];
  risk: Risk;
  start_at: string | null;
  end_at: string | null;
  seats_taken: number;
  appeal_note: string | null;
  published_at: string | null;
  form: EventForm;
  message?: string;
};

export type Reach = { count: number; free: number; interested: number; interest_label: string | null; ready: boolean };
export type Preview = { risk: Risk; outcome: { status: EventStatus; label: FeedItem["verification_label"] }; reach: Reach };

export type Extraction = {
  fields: Omit<EventForm, "area" | "capacity" | "skill_level" | "poster_url" | "source"> & {
    organizer_name: string | null;
    contact: string | null;
  };
  low_confidence: string[];
  source: "live" | "mock" | "cache";
  message: string | null;
  poster_url: string | null;
};

export type OrgSummary = {
  org_name: string;
  trust_level: string;
  upcoming: number;
  registrations: number;
  attendance_rate: number | null;
  followers: number;
  follower_growth: number[];
  slug: string;
};

export type ReviewItem = {
  id: string;
  title: string;
  description: string;
  status: EventStatus;
  start_at: string | null;
  fee_inr: number;
  registration_url: string | null;
  poster_url: string | null;
  risk_score: number;
  risk_reasons: string[];
  appeal_note: string | null;
  reports: { reason: string; at: string }[];
  organizer: { id: string; name: string; trust_level: string; email_domain: string } | null;
};
