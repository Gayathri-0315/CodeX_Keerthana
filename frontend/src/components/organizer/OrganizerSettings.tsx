import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Download, ImagePlus, ShieldCheck, Upload } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../../lib/api";
import { useUpdateMe } from "../../lib/queries";
import type { User } from "../../lib/types";
import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { useToast } from "../ui/Toaster";
import { Toggle } from "../ui/Toggle";

type Prefs = { new_registration: boolean; cancellation: boolean; waitlist_change: boolean; new_message: boolean; review_result: boolean; event_reminders: boolean };
type OrgType = "college_club" | "department" | "company" | "community" | "independent";
type Profile = {
  org_name: string;
  org_type: OrgType | null;
  college_or_company: string | null;
  city: string | null;
  bio: string | null;
  logo_url: string | null;
  phone: string | null;
  website: string | null;
  instagram: string | null;
  linkedin: string | null;
  show_official_email: boolean;
  official_email: string;
  trust_level: "new" | "verified" | "trusted";
  trust_label: string;
  faculty_name: string | null;
  faculty_email: string | null;
  verification: { status: "pending" | "approved" | "rejected"; submitted_at: string; document_type: string } | null;
  track_record: { events_hosted: number; attendance_rate: number | null; response_time_hours: number | null };
  notif_prefs: Prefs;
  daily_digest: boolean;
};

const KEY = ["org", "profile"] as const;
const inputCls =
  "h-12 w-full rounded-[14px] bg-surface-2 px-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]";

function Section({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <section className="mb-8">
      <h2 className="footnote mb-2 px-1 font-semibold uppercase tracking-wide text-text-2">{title}</h2>
      <div className="card divide-y divide-line px-5 py-1">{children}</div>
      {note && <p className="footnote mt-2 px-1 text-text-2">{note}</p>}
    </section>
  );
}

function Row({ children }: { children: ReactNode }) {
  return <div className="py-4">{children}</div>;
}

function useProfile() {
  return useQuery({ queryKey: KEY, queryFn: () => api<Profile>("/organizer/profile") });
}

function useSaveProfile() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (patch: Partial<Profile>) => api<Profile>("/organizer/profile", { method: "PATCH", body: patch }),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: KEY });
      const prev = qc.getQueryData<Profile>(KEY);
      if (prev) qc.setQueryData(KEY, { ...prev, ...patch });
      return { prev };
    },
    onError: (e, _p, ctx) => {
      if (ctx?.prev) qc.setQueryData(KEY, ctx.prev);
      toast({ tone: "error", title: "Couldn't save", body: (e as Error).message });
    },
    onSuccess: (p) => {
      qc.setQueryData(KEY, p);
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

/** A text field that saves when you leave it (only if it changed). */
function TextRow({ label, value, field, max, type = "text", placeholder, hint, multiline }: {
  label: string;
  value: string | null;
  field: keyof Profile;
  max: number;
  type?: string;
  placeholder?: string;
  hint?: string;
  multiline?: boolean;
}) {
  const save = useSaveProfile();
  const [v, setV] = useState(value ?? "");
  const last = useRef(value ?? "");
  useEffect(() => {
    setV(value ?? "");
    last.current = value ?? "";
  }, [value]);
  const id = `org-${String(field)}`;
  const commit = () => {
    if (v.trim() === last.current) return;
    last.current = v.trim();
    save.mutate({ [field]: v.trim() || null } as Partial<Profile>);
  };
  return (
    <Row>
      <label htmlFor={id} className="footnote mb-1.5 block font-medium text-text-2">{label}</label>
      {multiline ? (
        <textarea id={id} value={v} maxLength={max} rows={3} placeholder={placeholder} onChange={(e) => setV(e.target.value)} onBlur={commit}
          className={`${inputCls} h-auto py-3`} />
      ) : (
        <input id={id} type={type} value={v} maxLength={max} placeholder={placeholder} onChange={(e) => setV(e.target.value)} onBlur={commit} className={inputCls} />
      )}
      {hint && <p className="footnote mt-1.5 text-text-2">{hint}</p>}
    </Row>
  );
}

export function OrganizerSettings({ me, patchMe }: { me: User; patchMe: (p: Partial<User>, saved?: string) => void }) {
  const { data: p, isPending, isError, refetch } = useProfile();
  if (isPending) return <div className="skeleton mb-8 h-96 rounded-[22px]" aria-busy="true" />;
  if (isError) {
    return (
      <div className="card mb-8 p-6 text-center">
        <p className="headline">Couldn't load your organizer profile.</p>
        <Button variant="secondary" className="mt-4" onClick={() => refetch()}>Try again</Button>
      </div>
    );
  }
  return (
    <>
      <ProfileSection p={p} />
      <TrustSection p={p} />
      <NotificationsSection p={p} me={me} patchMe={patchMe} />
    </>
  );
}

// ---------------- 1. Profile ----------------

const ORG_TYPES: { value: OrgType; label: string }[] = [
  { value: "college_club", label: "College club" },
  { value: "department", label: "Department" },
  { value: "company", label: "Company" },
  { value: "community", label: "Community" },
  { value: "independent", label: "Independent" },
];

function ProfileSection({ p }: { p: Profile }) {
  const save = useSaveProfile();
  const qc = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const uploadLogo = async (file: File) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      qc.setQueryData(KEY, await api<Profile>("/organizer/profile/logo", { form }));
      toast({ tone: "success", title: "Logo updated" });
    } catch (e) {
      toast({ tone: "error", title: "Couldn't upload the logo", body: (e as Error).message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Section title="Profile" note="Students see this on your event pages. Links help them trust you.">
      <Row>
        <div className="flex items-center gap-4">
          <span className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-[18px] bg-accent-soft text-accent">
            {p.logo_url ? <img src={p.logo_url} alt="" width={64} height={64} className="size-full object-cover" /> : <span className="title-3">{p.org_name[0]?.toUpperCase()}</span>}
          </span>
          <div className="flex flex-wrap gap-2">
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" aria-label="Upload a logo"
              onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])} />
            <Button size="sm" variant="secondary" loading={uploading} onClick={() => fileRef.current?.click()}>
              <ImagePlus className="size-4" aria-hidden />{p.logo_url ? "Change logo" : "Add logo"}
            </Button>
            {p.logo_url && (
              <Button size="sm" variant="quiet" onClick={async () => qc.setQueryData(KEY, await api<Profile>("/organizer/profile/logo", { method: "DELETE" }))}>
                Remove
              </Button>
            )}
          </div>
        </div>
      </Row>
      <TextRow label="Organization or club name" field="org_name" value={p.org_name} max={160} />
      <Row>
        <label htmlFor="org-type" className="footnote mb-1.5 block font-medium text-text-2">Type</label>
        <select id="org-type" value={p.org_type ?? ""} onChange={(e) => save.mutate({ org_type: (e.target.value || null) as OrgType | null })} className={inputCls}>
          <option value="">Choose a type</option>
          {ORG_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </Row>
      <TextRow label="College or company" field="college_or_company" value={p.college_or_company} max={160} />
      <TextRow label="City" field="city" value={p.city} max={80} placeholder="e.g. Coimbatore" />
      <TextRow label="Short bio" field="bio" value={p.bio} max={500} multiline placeholder="What your club does, in a sentence or two." />
      <Row>
        <p className="footnote mb-1.5 font-medium text-text-2">Official email</p>
        <p className="body flex flex-wrap items-center gap-2">
          {p.official_email}
          {p.trust_level !== "new" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2.5 py-0.5 footnote font-medium text-success-text">
              <BadgeCheck className="size-3.5" aria-hidden />Verified
            </span>
          )}
        </p>
        <p className="footnote mt-1 text-text-2">This is the email you sign in with.</p>
      </Row>
      <TextRow label="Phone (optional)" field="phone" value={p.phone} max={32} type="tel" />
      <TextRow label="Website" field="website" value={p.website} max={300} type="url" placeholder="https://" />
      <TextRow label="Instagram" field="instagram" value={p.instagram} max={300} type="url" placeholder="https://instagram.com/yourclub" />
      <TextRow label="LinkedIn" field="linkedin" value={p.linkedin} max={300} type="url" placeholder="https://linkedin.com/company/yourclub" />
      <Row>
        <p className="footnote mb-1.5 font-medium text-text-2">How students can contact you</p>
        <Segmented
          label="Public contact"
          className="w-full"
          value={p.show_official_email ? "email" : "messages"}
          onChange={(v) => save.mutate({ show_official_email: v === "email" })}
          options={[{ value: "messages", label: "In-app messages only" }, { value: "email", label: "Also show my email" }]}
        />
      </Row>
    </Section>
  );
}

// ---------------- 2. Trust and verification ----------------

const DOC_TYPES = [
  { value: "college_id", label: "College ID" },
  { value: "faculty_letter", label: "Faculty approval letter" },
  { value: "company_proof", label: "Company proof (offer letter, ID or email)" },
  { value: "other", label: "Something else" },
];
const TRUST_COPY: Record<Profile["trust_level"], string> = {
  new: "New organizers' first events and every internship are reviewed by our team before they go live.",
  verified: "Your events show a Verified organizer label and publish straight away when they pass the checks.",
  trusted: "You've run events with good attendance. Your events publish straight away.",
};

function TrustSection({ p }: { p: Profile }) {
  const t = p.track_record;
  return (
    <Section title="Trust and verification">
      <Row>
        <div className="flex items-center gap-3">
          <ShieldCheck className={`size-6 shrink-0 ${p.trust_level === "new" ? "text-text-2" : "text-success-text"}`} aria-hidden />
          <div>
            <p className="headline">{p.trust_label}</p>
            <p className="footnote text-text-2">{TRUST_COPY[p.trust_level]}</p>
          </div>
        </div>
      </Row>
      {p.trust_level === "new" && <VerifyRow p={p} />}
      <TextRow label="Faculty coordinator name" field="faculty_name" value={p.faculty_name} max={120} hint="Useful for college events." />
      <TextRow label="Faculty coordinator email" field="faculty_email" value={p.faculty_email} max={255} type="email" />
      <Row>
        <p className="footnote mb-2 font-medium text-text-2">Track record (worked out by ShowUp)</p>
        <dl className="grid grid-cols-3 gap-2 text-center">
          <Stat label="Events hosted" value={String(t.events_hosted)} />
          <Stat label="Avg attendance" value={t.attendance_rate == null ? "Not yet" : `${Math.round(t.attendance_rate * 100)}%`} />
          <Stat label="Replies within" value={t.response_time_hours == null ? "Not yet" : `${t.response_time_hours} h`} />
        </dl>
      </Row>
    </Section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] bg-surface-2 px-2 py-3">
      <dd className="headline tnum">{value}</dd>
      <dt className="footnote text-text-2">{label}</dt>
    </div>
  );
}

function VerifyRow({ p }: { p: Profile }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [docType, setDocType] = useState("college_id");
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const v = p.verification;

  if (v?.status === "pending") {
    return (
      <Row>
        <p className="body">Verification sent for review</p>
        <p className="footnote text-text-2">Our team will check your document and let you know the result.</p>
      </Row>
    );
  }
  const send = async () => {
    if (!file) return;
    setSending(true);
    try {
      const form = new FormData();
      form.append("document_type", docType);
      form.append("note", note);
      form.append("file", file);
      qc.setQueryData(KEY, await api<Profile>("/organizer/profile/verification", { form }));
      toast({ tone: "success", title: "Sent for review", body: "We'll tell you when it's checked." });
    } catch (e) {
      toast({ tone: "error", title: "Couldn't send", body: (e as Error).message });
    } finally {
      setSending(false);
    }
  };
  return (
    <Row>
      <p className="body">Verify your organization</p>
      <p className="footnote mb-3 text-text-2">
        {v?.status === "rejected" ? "Your last document couldn't be verified. You can send another. " : ""}
        Only our review team sees the document.
      </p>
      <div className="flex flex-col gap-3">
        <select aria-label="Document type" value={docType} onChange={(e) => setDocType(e.target.value)} className={inputCls}>
          {DOC_TYPES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <label className={`pressable flex min-h-12 cursor-pointer items-center gap-2 rounded-[14px] px-4 callout shadow-[inset_0_0_0_1px_var(--line)] ${file ? "text-text" : "text-text-2"}`}>
          <Upload className="size-4 shrink-0" aria-hidden />
          <span className="truncate">{file ? file.name : "Choose an image or PDF (up to 8 MB)"}</span>
          <input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <input aria-label="Note for the reviewer (optional)" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)}
          placeholder="Note for the reviewer (optional)" className={inputCls} />
        <Button disabled={!file} loading={sending} onClick={send}>Send for review</Button>
      </div>
    </Row>
  );
}

// ---------------- 3. Notifications ----------------

const PREF_ROWS: { key: keyof Prefs; label: string; description?: string }[] = [
  { key: "new_registration", label: "New registration" },
  { key: "cancellation", label: "Cancellation" },
  { key: "waitlist_change", label: "Waitlist changes", description: "Someone joins the waitlist or takes an open seat." },
  { key: "new_message", label: "New student message" },
  { key: "review_result", label: "Review results", description: "When our team approves or declines an event or verification." },
  { key: "event_reminders", label: "Event reminders", description: "A day before each of your events." },
];

function NotificationsSection({ p, me, patchMe }: { p: Profile; me: User; patchMe: (x: Partial<User>, saved?: string) => void }) {
  const save = useSaveProfile();
  const update = useUpdateMe();
  return (
    <Section title="Notifications" note="Telegram alerts aren't available; ShowUp sends alerts in the app and by email.">
      {PREF_ROWS.map((r) => (
        <Toggle key={r.key} label={r.label} description={r.description} checked={p.notif_prefs[r.key]}
          onChange={(v) => save.mutate({ notif_prefs: { ...p.notif_prefs, [r.key]: v } })} />
      ))}
      <Toggle
        label="Daily digest"
        description="One summary at 7 PM instead of an alert for every registration, cancellation and waitlist change."
        checked={p.daily_digest}
        onChange={(v) => save.mutate({ daily_digest: v })}
      />
      <Toggle label="In-app" checked={!!me.notif_channels.in_app} onChange={(v) => patchMe({ notif_channels: { ...me.notif_channels, in_app: v } })} />
      <Toggle label="Email" description={me.email} checked={!!me.notif_channels.email} onChange={(v) => patchMe({ notif_channels: { ...me.notif_channels, email: v } })} />
      <Row>
        <p className="body">Quiet hours</p>
        <div className="mt-2 flex items-center gap-2">
          <TimeField label="Quiet from" value={me.quiet_hours_start} onChange={(v) => update.mutate({ quiet_hours_start: v })} />
          <span className="text-text-2">to</span>
          <TimeField label="Quiet until" value={me.quiet_hours_end} onChange={(v) => update.mutate({ quiet_hours_end: v })} />
        </div>
      </Row>
    </Section>
  );
}

function TimeField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <input type="time" aria-label={label} value={v} onChange={(e) => setV(e.target.value)} onBlur={() => v && v !== value && onChange(v)}
      className="h-11 rounded-[12px] bg-surface-2 px-3 body tnum shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]" />
  );
}

// ---------------- Account: readable data download ----------------

export function DownloadMyData() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      const res = await fetch("/api/organizer/profile/export", { credentials: "same-origin" });
      if (!res.ok) throw new Error("Try again in a moment.");
      const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "showup-data.txt";
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: name });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast({ tone: "error", title: "Couldn't download your data", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="secondary" loading={busy} onClick={download}>
      <Download className="size-4" aria-hidden />Download my data
    </Button>
  );
}
