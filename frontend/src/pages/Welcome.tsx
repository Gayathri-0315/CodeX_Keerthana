import { AnimatePresence, m } from "motion/react";
import { ArrowLeft, CalendarDays, MapPin, ScanLine } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { Field } from "../components/ui/Field";
import { BudgetPicker, DistanceSlider, AreaPicker } from "../components/PlaceControls";
import { useToast } from "../components/ui/Toaster";
import { INTERESTS } from "../lib/constants";
import { spring } from "../lib/motion";
import { useMe, useUpdateInterests, useUpdateMe } from "../lib/queries";
import { openAuth } from "../lib/authModal";
import type { Area } from "../lib/types";

/** Onboarding after sign-up (the landing page and sign-in popup come before it). */
type Step = "interests" | "place" | "free";
const ORDER: Step[] = ["interests", "place", "free"];

export default function Welcome() {
  const { data: me, isPending } = useMe();
  const [step, setStep] = useState<Step>("interests");
  const [dir, setDir] = useState(1);

  useEffect(() => {
    if (!isPending && !me) openAuth({ audience: "student", mode: "signup" });
  }, [isPending, me]);

  if (isPending) return <div className="min-h-dvh" />;
  if (!me) return <Navigate to="/" replace />;
  if (me.onboarded || me.role !== "student") return <Navigate to="/" replace />;

  const go = (s: Step) => {
    setDir(ORDER.indexOf(s) >= ORDER.indexOf(step) ? 1 : -1);
    setStep(s);
  };
  const progress = ORDER.indexOf(step);

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col px-5 safe-top">
      <div className="flex h-16 items-center justify-between">
        {step !== "interests" ? (
          <button
            aria-label="Back"
            className="pressable -ml-2 grid size-11 place-items-center rounded-full text-accent"
            onClick={() => go(ORDER[ORDER.indexOf(step) - 1])}
          >
            <ArrowLeft className="size-6" />
          </button>
        ) : (
          <span />
        )}
        {progress >= 0 && (
          <div className="flex gap-1.5" aria-label={`Step ${progress + 1} of 3`} role="img">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={`h-2 rounded-full transition-all duration-300 ${i === progress ? "w-6 bg-accent-fill" : i < progress ? "w-2 bg-accent/50" : "w-2 bg-text/15"}`}
              />
            ))}
          </div>
        )}
        <span className="w-11" />
      </div>

      <div className="relative flex flex-1 flex-col">
        <AnimatePresence mode="popLayout" initial={false} custom={dir}>
          <m.section
            key={step}
            custom={dir}
            variants={{
              enter: (d: number) => ({ x: d * 40, opacity: 0 }),
              center: { x: 0, opacity: 1 },
              exit: (d: number) => ({ x: d * -40, opacity: 0 }),
            }}
            initial="enter"
            animate="center"
            exit="exit"
            transition={spring}
            className="flex flex-1 flex-col pb-8"
          >
            {step === "interests" && <Interests onDone={() => go("place")} />}
            {step === "place" && <Place onDone={() => go("free")} />}
            {step === "free" && <Free />}
          </m.section>
        </AnimatePresence>
      </div>
    </div>
  );
}

function StepTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6 mt-2">
      <h1 className="title-1">{title}</h1>
      {subtitle && <p className="body mt-2 text-text-2">{subtitle}</p>}
    </div>
  );
}

function Footer({ children }: { children: ReactNode }) {
  return <div className="mt-auto flex flex-col gap-2 pt-6">{children}</div>;
}

function Interests({ onDone }: { onDone: () => void }) {
  const { data: me } = useMe();
  const save = useUpdateInterests();
  const toast = useToast();
  const [picked, setPicked] = useState<Set<string>>(() => new Set(me?.interests.map((i) => i.tag)));
  const [text, setText] = useState(me?.interest_text ?? "");

  const toggle = (id: string) =>
    setPicked((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const next = () =>
    save.mutate(
      { interests: [...picked].map((tag) => ({ tag, weight: 2 })), interest_text: text },
      { onSuccess: onDone, onError: (e) => toast({ tone: "error", title: "Couldn't save", body: (e as Error).message }) },
    );

  return (
    <>
      <StepTitle title="What do you like?" subtitle="Pick a few. We'll only suggest events that match." />
      <div className="flex flex-wrap gap-2">
        {INTERESTS.map((i) => (
          <Chip key={i.id} label={i.label} selected={picked.has(i.id)} onToggle={() => toggle(i.id)} />
        ))}
      </div>
      <Field className="mt-6" label="Anything else?" placeholder="e.g. Flutter, chess, startup funding" value={text} maxLength={500} onChange={(e) => setText(e.target.value)} />
      <Footer>
        <Button size="lg" full onClick={next} disabled={picked.size === 0 && !text.trim()} loading={save.isPending}>
          Continue
        </Button>
      </Footer>
    </>
  );
}

function Place({ onDone }: { onDone: () => void }) {
  const { data: me } = useMe();
  const update = useUpdateMe();
  const toast = useToast();
  const [area, setArea] = useState<Area | null>(
    me?.home_area && me.home_lat != null && me.home_lng != null ? { name: me.home_area, lat: me.home_lat, lng: me.home_lng } : null,
  );
  const [distance, setDistance] = useState<number | null>(me ? me.max_distance_km : 20);
  const [budget, setBudget] = useState<number | null>(me?.budget_max_inr ?? 200);

  const next = () =>
    update.mutate(
      { home_area: area?.name ?? null, home_lat: area?.lat ?? null, home_lng: area?.lng ?? null, max_distance_km: distance, budget_max_inr: budget },
      { onSuccess: onDone, onError: (e) => toast({ tone: "error", title: "Couldn't save", body: (e as Error).message }) },
    );

  return (
    <>
      <StepTitle title="Where and how much?" subtitle="We'll skip events that are too far or over budget." />
      <div className="flex flex-col gap-7">
        <div>
          <p className="footnote mb-1.5 flex items-center gap-1 font-medium text-text-2"><MapPin className="size-4" aria-hidden /> Your area</p>
          <AreaPicker value={area} onChange={setArea} />
        </div>
        <DistanceSlider value={distance} onChange={setDistance} />
        <BudgetPicker value={budget} onChange={setBudget} />
      </div>
      <Footer>
        <Button size="lg" full onClick={next} disabled={!area} loading={update.isPending}>Continue</Button>
      </Footer>
    </>
  );
}

function Free() {
  const navigate = useNavigate();
  const update = useUpdateMe();
  return (
    <>
      <StepTitle title="When are you free?" subtitle="We only show events that fit these hours, travel time included." />
      <button
        onClick={() => navigate("/calendar?onboarding=1&import=1")}
        className="pressable liftable card mb-3 flex items-center gap-4 p-5 text-left"
      >
        <span className="grid size-12 shrink-0 place-items-center rounded-[14px] bg-accent-soft text-accent">
          <ScanLine className="size-6" aria-hidden />
        </span>
        <span>
          <span className="headline block">Upload my timetable</span>
          <span className="callout block text-text-2">Snap your class timetable. We'll find the gaps.</span>
        </span>
      </button>
      <button
        onClick={() => navigate("/calendar?onboarding=1")}
        className="pressable liftable card flex items-center gap-4 p-5 text-left"
      >
        <span className="grid size-12 shrink-0 place-items-center rounded-[14px] bg-success/15 text-success-text">
          <CalendarDays className="size-6" aria-hidden />
        </span>
        <span>
          <span className="headline block">Tap my free time</span>
          <span className="callout block text-text-2">Paint your free hours on a weekly grid.</span>
        </span>
      </button>
      <Footer>
        <Button
          variant="quiet"
          full
          loading={update.isPending}
          onClick={() => update.mutate({ onboarded: true }, { onSuccess: () => navigate("/") })}
        >
          I'll do this later
        </Button>
      </Footer>
    </>
  );
}
