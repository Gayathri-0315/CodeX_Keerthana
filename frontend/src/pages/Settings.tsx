import { Download, LogOut, Minus, Plus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { LegalLinks } from "../components/LegalLinks";
import { PageHeader } from "../components/AppShell";
import { AreaPicker, BudgetPicker, DistanceSlider } from "../components/PlaceControls";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { Segmented } from "../components/ui/Segmented";
import { Sheet } from "../components/ui/Sheet";
import { useToast } from "../components/ui/Toaster";
import { Toggle } from "../components/ui/Toggle";
import { api } from "../lib/api";
import { INTERESTS } from "../lib/constants";
import { formatTime } from "../lib/format";
import { useMe, useSignOut, useUpdateInterests, useUpdateMe } from "../lib/queries";
import { getTheme, setTheme, type ThemeChoice } from "../lib/theme";
import type { User } from "../lib/types";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="footnote mb-2 px-1 font-semibold uppercase tracking-wide text-text-2">{title}</h2>
      <div className="card divide-y divide-line px-5 py-1">{children}</div>
    </section>
  );
}

function Row({ children }: { children: ReactNode }) {
  return <div className="py-4">{children}</div>;
}

export default function Settings() {
  const { data: me } = useMe();
  const update = useUpdateMe();
  const toast = useToast();
  if (!me) return null;

  const patch = (p: Partial<User>, saved = "Saved") =>
    update.mutate(p, {
      onSuccess: () => toast({ tone: "success", title: saved }),
      onError: (e) => toast({ tone: "error", title: "Couldn't save", body: (e as Error).message }),
    });

  return (
    <>
      <PageHeader title="Settings" />
      <div className="mx-auto max-w-2xl">
        {me.role === "student" && (
          <>
            <InterestsSection me={me} />
            <PlaceSection me={me} patch={patch} />
            <Section title="Matching">
              <Toggle
                label="Only events that fit my free time"
                description="Turn off to also see events outside your free hours."
                checked={me.strict_schedule}
                onChange={(v) => patch({ strict_schedule: v })}
              />
              <Toggle
                label="Show “Almost” events"
                description="Interesting events that clash with your schedule, with the reason."
                checked={me.show_almost}
                onChange={(v) => patch({ show_almost: v })}
              />
              <Row>
                <p className="footnote mb-1.5 font-medium text-text-2">Format</p>
                <Segmented
                  label="Format"
                  className="w-full"
                  value={me.format_pref}
                  onChange={(v) => patch({ format_pref: v })}
                  options={[{ value: "in_person", label: "In person" }, { value: "online", label: "Online" }, { value: "either", label: "Either" }]}
                />
              </Row>
              <Row>
                <p className="footnote mb-1.5 font-medium text-text-2">Skill level</p>
                <Segmented
                  label="Skill level"
                  className="w-full"
                  value={me.skill_level}
                  onChange={(v) => patch({ skill_level: v })}
                  options={[{ value: "beginner", label: "Beginner" }, { value: "intermediate", label: "Intermediate" }, { value: "advanced", label: "Advanced" }]}
                />
              </Row>
            </Section>
            <AlertsSection me={me} patch={patch} />
          </>
        )}
        <AppearanceSection />
        <DataSection me={me} />
        <LegalLinks className="mb-8 px-1" />
      </div>
    </>
  );
}

function InterestsSection({ me }: { me: User }) {
  const save = useUpdateInterests();
  const toast = useToast();
  const [text, setText] = useState(me.interest_text);
  const picked = new Set(me.interests.map((i) => i.tag));

  const commit = (tags: Set<string>, interest_text = text) =>
    save.mutate(
      { interests: [...tags].map((tag) => ({ tag, weight: me.interests.find((i) => i.tag === tag)?.weight ?? 2 })), interest_text },
      { onError: (e) => toast({ tone: "error", title: "Couldn't save interests", body: (e as Error).message }) },
    );

  return (
    <Section title="Interests">
      <Row>
        <div className="flex flex-wrap gap-2">
          {INTERESTS.map((i) => (
            <Chip
              key={i.id}
              label={i.label}
              selected={picked.has(i.id)}
              onToggle={() => {
                const n = new Set(picked);
                n.has(i.id) ? n.delete(i.id) : n.add(i.id);
                commit(n);
              }}
            />
          ))}
        </div>
      </Row>
      <Row>
        <label htmlFor="interest-text" className="footnote mb-1.5 block font-medium text-text-2">Anything else?</label>
        <input
          id="interest-text"
          value={text}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => text !== me.interest_text && commit(picked, text)}
          placeholder="e.g. Flutter, chess, startup funding"
          className="h-12 w-full rounded-[14px] bg-surface-2 px-4 body shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
        />
      </Row>
    </Section>
  );
}

function PlaceSection({ me, patch }: { me: User; patch: (p: Partial<User>) => void }) {
  const [distance, setDistance] = useState(me.max_distance_km);
  useEffect(() => setDistance(me.max_distance_km), [me.max_distance_km]);
  const area = me.home_area && me.home_lat != null && me.home_lng != null ? { name: me.home_area, lat: me.home_lat, lng: me.home_lng } : null;

  return (
    <Section title="Where and how much">
      <Row>
        <p className="footnote mb-1.5 font-medium text-text-2">Your area</p>
        <AreaPicker value={area} onChange={(a) => patch({ home_area: a.name, home_lat: a.lat, home_lng: a.lng })} />
      </Row>
      <Row>
        <DistanceSlider value={distance} onChange={setDistance} onCommit={(v) => v !== me.max_distance_km && patch({ max_distance_km: v })} />
      </Row>
      <Row>
        <BudgetPicker value={me.budget_max_inr} onChange={(v) => patch({ budget_max_inr: v })} />
      </Row>
    </Section>
  );
}

function AlertsSection({ me, patch }: { me: User; patch: (p: Partial<User>, saved?: string) => void }) {
  const pausedUntil = me.notif_paused_until ? new Date(me.notif_paused_until + "Z") : null; // API times are naive UTC
  const paused = pausedUntil && pausedUntil > new Date();
  const pauseFor = (days: number | null) => {
    const until = days == null ? new Date("2099-01-01T00:00:00Z") : new Date(Date.now() + days * 86400_000);
    patch({ notif_paused_until: until.toISOString().replace("Z", "") }, "Alerts paused");
  };

  return (
    <Section title="Alerts">
      <Toggle label="In-app" checked={!!me.notif_channels.in_app} onChange={(v) => patch({ notif_channels: { ...me.notif_channels, in_app: v } })} />
      <Toggle label="Email" description={me.email} checked={!!me.notif_channels.email} onChange={(v) => patch({ notif_channels: { ...me.notif_channels, email: v } })} />
      <Row>
        <div className="flex items-center justify-between gap-4">
          <span>
            <span className="body block">Max alerts per week</span>
            <span className="footnote block text-text-2">Urgent seat alerts can go one over.</span>
          </span>
          <Stepper value={me.notif_max_per_week} min={1} max={7} onChange={(v) => patch({ notif_max_per_week: v })} label="alerts per week" />
        </div>
      </Row>
      <Row>
        <p className="body">Quiet hours</p>
        <div className="mt-2 flex items-center gap-2">
          <TimeInput label="Quiet from" value={me.quiet_hours_start} onChange={(v) => patch({ quiet_hours_start: v })} />
          <span className="text-text-2">to</span>
          <TimeInput label="Quiet until" value={me.quiet_hours_end} onChange={(v) => patch({ quiet_hours_end: v })} />
        </div>
      </Row>
      <Row>
        <p className="body">Pause alerts</p>
        {paused ? (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <span className="callout text-text-2">
              {pausedUntil!.getUTCFullYear() > 2090
                ? "Paused until you turn them on."
                : `Paused until ${pausedUntil!.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "Asia/Kolkata" })}, ${formatTime(pausedUntil!)}.`}
            </span>
            <Button size="sm" variant="secondary" onClick={() => patch({ notif_paused_until: null }, "Alerts on")}>Turn on</Button>
          </div>
        ) : (
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => pauseFor(1)}>1 day</Button>
            <Button size="sm" variant="secondary" onClick={() => pauseFor(7)}>1 week</Button>
            <Button size="sm" variant="secondary" onClick={() => pauseFor(null)}>Until I turn on</Button>
          </div>
        )}
      </Row>
    </Section>
  );
}

function Stepper({ value, min, max, onChange, label }: { value: number; min: number; max: number; onChange: (v: number) => void; label: string }) {
  return (
    <div className="flex items-center rounded-full bg-text/6" role="group" aria-label={label}>
      <button aria-label="Fewer" className="pressable grid size-11 place-items-center rounded-full disabled:opacity-30" disabled={value <= min} onClick={() => onChange(value - 1)}>
        <Minus className="size-4" />
      </button>
      <span className="w-6 text-center headline tnum" aria-live="polite">{value}</span>
      <button aria-label="More" className="pressable grid size-11 place-items-center rounded-full disabled:opacity-30" disabled={value >= max} onClick={() => onChange(value + 1)}>
        <Plus className="size-4" />
      </button>
    </div>
  );
}

function TimeInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const [v, setV] = useState(value);
  const last = useRef(value);
  useEffect(() => {
    setV(value);
    last.current = value;
  }, [value]);
  return (
    <input
      type="time"
      aria-label={label}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v && v !== last.current && onChange(v)}
      className="h-11 rounded-[12px] bg-surface-2 px-3 body tnum shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
    />
  );
}

function AppearanceSection() {
  const [theme, set] = useState<ThemeChoice>(getTheme);
  return (
    <Section title="Appearance">
      <Row>
        <Segmented
          label="Theme"
          className="w-full"
          value={theme}
          onChange={(t) => {
            set(t);
            setTheme(t);
          }}
          options={[{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]}
        />
      </Row>
    </Section>
  );
}

function DataSection({ me }: { me: User }) {
  const signOut = useSignOut();
  const navigate = useNavigate();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const exportData = async () => {
    try {
      const data = await api<unknown>("/users/me/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = Object.assign(document.createElement("a"), { href: url, download: "showup-data.json" });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast({ tone: "error", title: "Couldn't export", body: (e as Error).message });
    }
  };

  const deleteAll = async () => {
    setDeleting(true);
    try {
      await api<void>("/users/me", { method: "DELETE" });
      signOut.reset();
      window.location.assign("/welcome");
    } catch (e) {
      setDeleting(false);
      toast({ tone: "error", title: "Couldn't delete", body: (e as Error).message });
    }
  };

  return (
    <Section title="Account">
      <Row>
        <p className="body">{me.name}</p>
        <p className="footnote text-text-2">{me.email}</p>
      </Row>
      <Row>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={exportData}><Download className="size-4" aria-hidden />Export my data</Button>
          <Button variant="secondary" loading={signOut.isPending} onClick={() => signOut.mutate(undefined, { onSuccess: () => navigate("/welcome") })}>
            <LogOut className="size-4" aria-hidden />Sign out
          </Button>
          <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="size-4" aria-hidden />Delete my data</Button>
        </div>
      </Row>
      <Sheet open={confirm} onClose={() => setConfirm(false)} title="Delete your data?">
        <p className="callout text-text-2">This removes your account, free time, registrations and alerts. It can't be undone.</p>
        <div className="mt-6 flex flex-col gap-2">
          <Button variant="danger" size="lg" full loading={deleting} onClick={deleteAll}>Delete everything</Button>
          <Button variant="quiet" size="lg" full onClick={() => setConfirm(false)}>Keep my account</Button>
        </div>
      </Sheet>
    </Section>
  );
}
