import { TriangleAlert } from "lucide-react";
import { createContext, useContext, type ReactNode } from "react";
import { Chip } from "../ui/Chip";
import { Segmented } from "../ui/Segmented";
import { INTERESTS } from "../../lib/constants";
import type { EventForm } from "../../lib/types";

const CATEGORIES = ["Workshop", "Meetup", "Hackathon", "Talk", "Conference", "Webinar", "Careers", "Volunteering", "Music", "Sports", "Photography", "Other"];
const ELIGIBILITY = [
  { id: "college_student", label: "College students" },
  { id: "year_4", label: "Final year only" },
  { id: "it_dept", label: "IT department" },
  { id: "cse_dept", label: "CSE department" },
];
const AREAS = ["Gandhipuram", "Peelamedu", "Saravanampatti", "RS Puram", "Singanallur", "Race Course", "Ganapathy", "Saibaba Colony",
  "Town Hall", "Ukkadam", "Kuniyamuthur", "Vadavalli", "Thudiyalur", "Kalapatti", "Hope College", "Avinashi Road", "Sulur", "Podanur"];

type Props = {
  form: EventForm;
  onChange: (patch: Partial<EventForm>, field: string) => void;
  /** Fields the AI wasn't sure about; highlighted until the organizer edits or leaves them. */
  check: Set<string>;
  onReviewed: (field: string) => void;
};

const inputCls =
  "h-12 w-full rounded-[14px] bg-surface-2 px-4 body text-text outline-none transition-shadow placeholder:text-text-2/70 focus:shadow-[inset_0_0_0_2px_var(--accent)]";

/** Leaving a flagged field counts as reviewing it, even if the value was already right. */
const Reviewed = createContext<(name: string) => void>(() => {});

function Field({ label, name, check, children, hint }: { label: string; name: string; check: Set<string>; children: ReactNode; hint?: string }) {
  const flagged = check.has(name);
  const reviewed = useContext(Reviewed);
  const onBlur = () => flagged && reviewed(name);
  return (
    <div>
      <label htmlFor={`ev-${name}`} className="footnote mb-1.5 flex items-center justify-between font-medium text-text-2">
        {label}
        {flagged && (
          <span className="inline-flex items-center gap-1 text-warning-text">
            <TriangleAlert className="size-3.5" aria-hidden /> Check this
          </span>
        )}
      </label>
      <div onBlur={onBlur} className={`rounded-[14px] ${flagged ? "shadow-[0_0_0_2px_var(--warning)]" : "shadow-[inset_0_0_0_1px_var(--line)]"}`}>{children}</div>
      {hint && <p className="footnote mt-1 text-text-2">{hint}</p>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="card mb-4 flex flex-col gap-4 p-5">
      <legend className="sr-only">{title}</legend>
      <p className="headline">{title}</p>
      {children}
    </fieldset>
  );
}

export function EventFormFields(props: Props) {
  return (
    <Reviewed.Provider value={props.onReviewed}>
      <Fields {...props} />
    </Reviewed.Provider>
  );
}

function Fields({ form, onChange, check }: Props) {
  const text = (name: keyof EventForm) => ({
    id: `ev-${name}`,
    value: (form[name] as string | null) ?? "",
    onChange: (e: { target: { value: string } }) => onChange({ [name]: e.target.value || null } as Partial<EventForm>, name),
  });
  const toggleIn = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  return (
    <>
      <Section title="Basics">
        <Field label="Title" name="title" check={check}>
          <input {...text("title")} value={form.title} onChange={(e) => onChange({ title: e.target.value }, "title")} maxLength={200} required className={inputCls} />
        </Field>
        <Field label="Description" name="description" check={check}>
          <textarea
            id="ev-description"
            value={form.description}
            onChange={(e) => onChange({ description: e.target.value }, "description")}
            maxLength={4000}
            rows={4}
            className={`${inputCls} h-auto py-3`}
          />
        </Field>
        <Field label="Category" name="category" check={check}>
          <select id="ev-category" value={form.category} onChange={(e) => onChange({ category: e.target.value }, "category")} className={inputCls}>
            <option value="">Choose a category</option>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Field>
        <div>
          <p className="footnote mb-1.5 font-medium text-text-2">Topics (up to 4)</p>
          <div className="flex flex-wrap gap-2">
            {INTERESTS.map((i) => (
              <Chip
                key={i.id}
                label={i.label}
                selected={form.tags.includes(i.id)}
                onToggle={() => {
                  if (!form.tags.includes(i.id) && form.tags.length >= 4) return;
                  onChange({ tags: toggleIn(form.tags, i.id) }, "tags");
                }}
              />
            ))}
          </div>
        </div>
      </Section>

      <Section title="When">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Date" name="date" check={check}>
            <input type="date" {...text("date")} className={`${inputCls} tnum`} />
          </Field>
          <Field label="Starts" name="start_time" check={check}>
            <input type="time" {...text("start_time")} className={`${inputCls} tnum`} />
          </Field>
          <Field label="Ends" name="end_time" check={check}>
            <input type="time" {...text("end_time")} className={`${inputCls} tnum`} />
          </Field>
        </div>
        <Field label="Registration closes" name="registration_deadline" check={check} hint="Leave empty to keep it open until the start.">
          <input type="date" {...text("registration_deadline")} className={`${inputCls} tnum`} />
        </Field>
      </Section>

      <Section title="Where">
        <Field label="Format" name="mode" check={check}>
          <Segmented
            label="Format"
            className="w-full"
            value={form.mode}
            onChange={(mode) => onChange({ mode }, "mode")}
            options={[{ value: "in_person", label: "In person" }, { value: "online", label: "Online" }, { value: "hybrid", label: "Hybrid" }]}
          />
        </Field>
        {form.mode !== "online" && (
          <>
            <Field label="Venue" name="venue_name" check={check}>
              <input {...text("venue_name")} maxLength={200} className={inputCls} placeholder="e.g. SNS Hall" />
            </Field>
            <Field label="Address" name="address" check={check}>
              <input {...text("address")} maxLength={300} className={inputCls} placeholder="Street and area" />
            </Field>
            <Field label="Area" name="area" check={check} hint="Used to work out travel time for students. We'll try the address if you skip this.">
              <select id="ev-area" value={form.area ?? ""} onChange={(e) => onChange({ area: e.target.value || null }, "area")} className={inputCls}>
                <option value="">Detect from address</option>
                {AREAS.map((a) => <option key={a}>{a}</option>)}
              </select>
            </Field>
          </>
        )}
      </Section>

      <Section title="Entry">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Fee (₹)" name="fee_inr" check={check} hint="0 means free.">
            <input
              id="ev-fee_inr"
              type="number"
              inputMode="numeric"
              min={0}
              value={form.fee_inr}
              onChange={(e) => onChange({ fee_inr: Math.max(0, Number(e.target.value) || 0) }, "fee_inr")}
              className={`${inputCls} tnum`}
            />
          </Field>
          <Field label="Seats" name="capacity" check={check} hint="Leave empty for no limit.">
            <input
              id="ev-capacity"
              type="number"
              inputMode="numeric"
              min={1}
              value={form.capacity ?? ""}
              onChange={(e) => onChange({ capacity: e.target.value ? Math.max(1, Number(e.target.value)) : null }, "capacity")}
              className={`${inputCls} tnum`}
            />
          </Field>
        </div>
        <Field label="Who can join" name="eligibility_text" check={check}>
          <input {...text("eligibility_text")} maxLength={200} className={inputCls} placeholder="e.g. Open to all college students" />
        </Field>
        <div>
          <p className="footnote mb-1.5 font-medium text-text-2">Only show to</p>
          <div className="flex flex-wrap gap-2">
            {ELIGIBILITY.map((t) => (
              <Chip key={t.id} label={t.label} selected={form.eligibility_tags.includes(t.id)} onToggle={() => onChange({ eligibility_tags: toggleIn(form.eligibility_tags, t.id) }, "eligibility_tags")} />
            ))}
          </div>
        </div>
        <Field label="Skill level" name="skill_level" check={check}>
          <Segmented
            label="Skill level"
            className="w-full"
            value={form.skill_level ?? "any"}
            onChange={(v) => onChange({ skill_level: v === "any" ? null : v }, "skill_level")}
            options={[{ value: "any", label: "Any" }, { value: "beginner", label: "Beginner" }, { value: "intermediate", label: "Intermediate" }, { value: "advanced", label: "Advanced" }]}
          />
        </Field>
        <Field label="External registration link (optional)" name="registration_url" check={check}>
          <input {...text("registration_url")} type="url" inputMode="url" maxLength={500} className={inputCls} placeholder="https://" />
        </Field>
      </Section>
    </>
  );
}

export const EMPTY_FORM: EventForm = {
  title: "", description: "", category: "", tags: [], date: null, start_time: null, end_time: null, mode: "in_person",
  venue_name: null, address: null, area: null, fee_inr: 0, capacity: null, registration_deadline: null,
  eligibility_text: null, eligibility_tags: [], skill_level: null, registration_url: null, poster_url: null,
  source: "form", field_confidence: {},
};
