import { AnimatePresence, m } from "motion/react";
import { ArrowLeft, Clock, ShieldX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EMPTY_FORM, EventFormFields } from "../../components/organizer/EventFormFields";
import { OutcomeHint, ReachPanel, TrustPanel } from "../../components/organizer/Panels";
import { PosterDrop, ReadingPoster } from "../../components/organizer/PosterDrop";
import { Button } from "../../components/ui/Button";
import { Sheet } from "../../components/ui/Sheet";
import { useToast } from "../../components/ui/Toaster";
import { ApiError } from "../../lib/api";
import { haptic, spring } from "../../lib/motion";
import { previewEvent, useAppeal, useExtractPoster, useOrgEvent, usePublishEvent } from "../../lib/organizer";
import type { EventForm, OrgEvent, Preview } from "../../lib/types";

type Step = "drop" | "reading" | "form" | "done";
const PREVIEW_DEBOUNCE_MS = 700;

function lowConfidence(conf: Record<string, number | null>, fields: Record<string, unknown>): Set<string> {
  const names = ["title", "description", "category", "date", "start_time", "end_time", "venue_name", "address", "fee_inr", "registration_deadline", "eligibility_text"];
  return new Set(names.filter((n) => fields[n] == null || fields[n] === "" || (conf[n] != null && conf[n]! < 0.7)));
}

export default function EventEditor() {
  const { id: editId } = useParams();
  const existing = useOrgEvent(editId);
  const navigate = useNavigate();
  const toast = useToast();
  const extract = useExtractPoster();
  const publish = usePublishEvent();

  const [step, setStep] = useState<Step>(editId ? "form" : "drop");
  const [id, setId] = useState<string | null>(editId ?? null);
  const [form, setForm] = useState<EventForm>(EMPTY_FORM);
  const [check, setCheck] = useState<Set<string>>(new Set());
  const [posterSrc, setPosterSrc] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<OrgEvent | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [checking, setChecking] = useState(false);

  // Editing: load once.
  const loaded = useRef(false);
  useEffect(() => {
    if (!existing.data || loaded.current) return;
    loaded.current = true;
    const f = existing.data.form;
    setForm(f);
    setPosterSrc(f.poster_url);
    if (f.source === "web_upload" && existing.data.status === "draft") setCheck(lowConfidence(f.field_confidence, f));
    if (existing.data.status === "blocked") setResult(existing.data);
  }, [existing.data]);

  // Live trust check + reach, debounced, cancelling stale requests.
  useEffect(() => {
    if (step !== "form" || (!form.title && !form.date)) return;
    const ctrl = new AbortController();
    setChecking(true);
    const t = window.setTimeout(() => {
      previewEvent(form, ctrl.signal)
        .then(setPreview)
        .catch((e) => (e as Error).name !== "AbortError" && setPreview(null))
        .finally(() => !ctrl.signal.aborted && setChecking(false));
    }, PREVIEW_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [form, step]);

  const onFile = (file: File) => {
    const local = URL.createObjectURL(file);
    setPosterSrc(file.type === "application/pdf" ? null : local);
    setStep("reading");
    extract.mutate(file, {
      onSuccess: (r) => {
        const f = r.fields;
        setForm({
          ...EMPTY_FORM,
          title: f.title ?? "",
          description: f.description ?? "",
          category: f.category ?? "",
          event_type: (f.event_type as EventForm["event_type"]) ?? "other",
          category_slug: f.category_slug ?? null,
          tags: f.tags.slice(0, 4),
          date: f.date,
          start_time: f.start_time,
          end_time: f.end_time,
          mode: f.mode ?? "in_person",
          venue_name: f.venue_name,
          address: f.address,
          fee_inr: f.fee_inr ?? 0,
          registration_deadline: f.registration_deadline,
          eligibility_text: f.eligibility_text,
          eligibility_tags: f.eligibility_tags,
          registration_url: f.registration_url,
          poster_url: r.poster_url,
          source: "web_upload",
          field_confidence: f.field_confidence,
        });
        // Type and category are suggestions: ask the organizer to confirm both.
        setCheck(new Set([...r.low_confidence.filter((n) => !["registration_url", "organizer_name", "mode", "category"].includes(n)), "event_type", "category_slug"]));
        if (r.poster_url) setPosterSrc(r.poster_url);
        setNotice(r.message);
        setStep("form");
      },
      onError: (e) => {
        setStep("drop");
        toast({ tone: "error", title: "Couldn't read that file", body: e instanceof ApiError ? e.message : "Try again." });
      },
    });
  };

  const reviewed = (field: string) =>
    setCheck((c) => {
      if (!c.has(field)) return c;
      const n = new Set(c);
      n.delete(field);
      return n;
    });
  const change = (patch: Partial<EventForm>, field: string) => {
    setForm((f) => ({ ...f, ...patch }));
    reviewed(field);
  };

  const submit = () =>
    publish.mutate(
      { id, form },
      {
        onSuccess: (event) => {
          setId(event.id);
          setResult(event);
          if (event.status === "blocked") {
            window.scrollTo({ top: 0, behavior: "smooth" });
            return;
          }
          haptic();
          setStep("done");
        },
        onError: (e) => toast({ tone: "error", title: "Couldn't publish", body: e instanceof ApiError ? e.message : "Check your connection and try again." }),
      },
    );

  if (editId && existing.isPending) return <div className="skeleton h-96 rounded-[22px]" />;
  if (editId && existing.isError) {
    return (
      <div className="card p-8 text-center">
        <p className="headline">Couldn't load this event.</p>
        <Link to="/" className="callout mt-2 inline-block text-accent">Back to dashboard</Link>
      </div>
    );
  }

  const pending = preview?.outcome.status === "pending_review";
  const blocked = result?.status === "blocked";

  return (
    <div className="pb-16">
      <Link to="/" className="pressable -ml-2 mb-3 inline-flex min-h-11 items-center gap-1 rounded-full px-2 callout font-medium text-accent">
        <ArrowLeft className="size-5" aria-hidden /> Dashboard
      </Link>

      <AnimatePresence mode="wait" initial={false}>
        {step === "drop" && (
          <m.div key="drop" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mx-auto max-w-xl">
            <h1 className="title-1 mb-6">New event</h1>
            <PosterDrop onFile={onFile} onManual={() => setStep("form")} />
          </m.div>
        )}

        {step === "reading" && (
          <m.div key="reading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="pt-6">
            {posterSrc ? <ReadingPoster src={posterSrc} /> : <p className="headline text-center">Reading your PDF...</p>}
          </m.div>
        )}

        {step === "form" && (
          <m.div key="form" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <h1 className="title-1 mb-2">{editId ? "Edit event" : "Check the details"}</h1>
            <p className="callout mb-6 text-text-2">
              {check.size > 0 ? `We weren't sure about ${check.size} ${check.size === 1 ? "field" : "fields"}. They're marked "Check this".` : "Review everything before publishing."}
            </p>

            {notice && <p className="callout mb-4 rounded-[14px] bg-accent-soft p-4 text-accent">{notice}</p>}
            {blocked && <BlockedBanner event={result!} onAppealed={setResult} />}

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
              <aside className="flex flex-col gap-4 lg:sticky lg:top-20 lg:self-start">
                {posterSrc && <img src={posterSrc} alt="Your poster" className="mx-auto max-h-[420px] w-auto rounded-[22px] shadow-card lg:max-h-[520px]" />}
                <div className="hidden flex-col gap-4 lg:flex">
                  <TrustPanel risk={preview?.risk ?? null} checking={checking} />
                  <ReachPanel preview={preview} />
                </div>
              </aside>
              <div>
                <EventFormFields form={form} onChange={change} check={check} onReviewed={reviewed} />
                <div className="flex flex-col gap-4 lg:hidden">
                  <TrustPanel risk={preview?.risk ?? null} checking={checking} />
                  <ReachPanel preview={preview} />
                </div>
                <div className="mt-6 flex flex-col gap-2">
                  <OutcomeHint preview={preview} />
                  <Button size="lg" full onClick={submit} loading={publish.isPending} disabled={!form.title.trim()}>
                    {existing.data?.status === "published" ? "Save changes" : blocked ? "Fix and retry" : pending ? "Submit for review" : "Publish"}
                  </Button>
                </div>
              </div>
            </div>
          </m.div>
        )}

        {step === "done" && result && (
          <m.div key="done" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={spring} className="mx-auto max-w-md pt-10 text-center">
            <Done status={result.status} />
            <h1 className="title-2 mt-6">{result.status === "published" ? "Your event is live" : "Submitted for review"}</h1>
            {result.status === "published" ? (
              preview?.reach.ready && <p className="callout mt-2 text-text-2">About {preview.reach.count} students will see it in their feed.</p>
            ) : (
              <p className="callout mt-2 text-text-2">{result.message}</p>
            )}
            <div className="mt-8 flex flex-col gap-2">
              <Button size="lg" full onClick={() => navigate("/")}>Back to dashboard</Button>
              {result.status === "published" && (
                <Button size="lg" variant="quiet" full onClick={() => navigate(`/event/${result.id}`)}>See it as students do</Button>
              )}
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Done({ status }: { status: string }) {
  const live = status === "published";
  return (
    <span className={`mx-auto grid size-24 place-items-center rounded-full text-white ${live ? "bg-success" : "bg-warning"}`}>
      {live ? (
        <svg viewBox="0 0 24 24" className="size-12" aria-hidden>
          <m.path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, delay: 0.15 }} />
        </svg>
      ) : (
        <Clock className="size-11" aria-hidden />
      )}
    </span>
  );
}

function BlockedBanner({ event, onAppealed }: { event: OrgEvent; onAppealed: (e: OrgEvent) => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const appeal = useAppeal();
  const toast = useToast();
  return (
    <div className="mb-6 rounded-[22px] bg-danger/12 p-5 text-danger-text" role="alert">
      <div className="flex items-start gap-3">
        <ShieldX className="mt-0.5 size-6 shrink-0" aria-hidden />
        <div className="flex-1">
          <p className="headline">We couldn't publish this event</p>
          <ul className="callout mt-2 list-disc space-y-1 pl-5">
            {event.risk.reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
          <p className="footnote mt-3">Fix the details below and try again. If you think this is a mistake, you can appeal.</p>
          <Button size="sm" variant="secondary" className="mt-2" onClick={() => setOpen(true)}>Appeal</Button>
        </div>
      </div>
      <Sheet open={open} onClose={() => setOpen(false)} title="Appeal this decision">
        <label htmlFor="appeal" className="callout text-text-2">Tell the reviewer why this event is genuine.</label>
        <textarea
          id="appeal"
          rows={4}
          value={note}
          maxLength={500}
          onChange={(e) => setNote(e.target.value)}
          className="mt-2 w-full rounded-[14px] bg-surface-2 p-3 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
        />
        <Button
          size="lg"
          full
          className="mt-4"
          disabled={note.trim().length < 5}
          loading={appeal.isPending}
          onClick={() =>
            appeal.mutate(
              { id: event.id, note },
              {
                onSuccess: (e) => {
                  setOpen(false);
                  onAppealed(e);
                  toast({ tone: "success", title: "Appeal sent", body: "An admin will review it." });
                },
                onError: (e) => toast({ tone: "error", title: "Couldn't send appeal", body: (e as Error).message }),
              },
            )
          }
        >
          Send appeal
        </Button>
      </Sheet>
    </div>
  );
}
