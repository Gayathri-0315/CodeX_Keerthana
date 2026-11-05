import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { ArrowLeft, CalendarCheck, Megaphone, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { closeAuth, useAuthModal, type Intent, type Mode, type Side } from "../../lib/authModal";
import { spring } from "../../lib/motion";
import { useForgotPassword, useRegister, useRegisterOrganizer, useSignIn } from "../../lib/queries";
import type { Registration, User } from "../../lib/types";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { Segmented } from "../ui/Segmented";
import { useToast } from "../ui/Toaster";
import { InOverlay } from "../ui/overlay";

const SIDES: Record<Side, { title: string; line: string; icon: typeof Megaphone }> = {
  student: { title: "Discover events", line: "Find events that fit your free time.", icon: CalendarCheck },
  organizer: { title: "Create events", line: "Reach students who can actually attend.", icon: Megaphone },
};

const message = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

/**
 * Sign in / sign up popup. When we know who the person is (they tapped Register, Save, Create an event...)
 * it shows only that panel, with a small link to switch. Only the top-nav "Sign in" (audience "unknown")
 * shows "Discover events" and "Create events" side by side (a Student | Organizer switch on phones).
 * The panel decides the role; the server enforces it.
 */
export function AuthModal() {
  const { open, audience, mode, intent, seq } = useAuthModal();
  const wide = useMediaQuery("(min-width: 768px)");
  const split = audience === "unknown";
  const panel = useRef<HTMLDivElement>(null);
  const finish = useFinish();

  // Esc closes; focus moves in, and back to where it was on close.
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => panel.current?.querySelector<HTMLElement>("[data-autofocus] input, input")?.focus(), 60);
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && closeAuth();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prev?.focus?.();
    };
  }, [open]);

  // Focus trap: Tab cycles inside the dialog.
  const trap = (e: KeyboardEvent) => {
    if (e.key !== "Tab" || !panel.current) return;
    const items = [...panel.current.querySelectorAll<HTMLElement>("button, input, a[href], select, [tabindex]:not([tabindex='-1'])")]
      .filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const onAuthed = (user: User, isNew: boolean) => finish(user, isNew, intent);

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-stretch justify-center md:items-center md:p-6" onKeyDown={trap}>
          <m.div
            className="absolute inset-0 bg-black/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={closeAuth}
          />
          <InOverlay.Provider value>
          <m.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label="Sign in to ShowUp"
            className={`relative flex w-full flex-col overflow-y-auto bg-surface shadow-card md:max-h-[calc(100dvh-48px)] md:rounded-[22px] ${split ? "md:max-w-[880px]" : "md:max-w-[440px]"}`}
            initial={wide ? { opacity: 0, scale: 0.96, y: 12 } : { y: "100%" }}
            animate={wide ? { opacity: 1, scale: 1, y: 0 } : { y: 0 }}
            exit={wide ? { opacity: 0, scale: 0.97, y: 8 } : { y: "100%" }}
            transition={spring}
          >
            {(wide || !split) && (
              <button onClick={closeAuth} aria-label="Close" className="pressable absolute right-3 top-3 z-10 grid size-11 place-items-center rounded-full text-text-2 hover:bg-text/6">
                <X className="size-5" />
              </button>
            )}
            {split && wide ? (
              <div className="grid grid-cols-2 divide-x divide-line">
                <SidePanel side="student" initialMode="signin" autoFocus onAuthed={onAuthed} />
                <SidePanel side="organizer" initialMode="signin" autoFocus={false} onAuthed={onAuthed} />
              </div>
            ) : split ? (
              <PhoneSplit key={seq} onAuthed={onAuthed} />
            ) : (
              <SinglePanel key={seq} audience={audience} mode={mode} onAuthed={onAuthed} />
            )}
          </m.div>
          </InOverlay.Provider>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Phones, unknown audience: a Student | Organizer switch at the top. */
function PhoneSplit({ onAuthed }: { onAuthed: (u: User, isNew: boolean) => void }) {
  const [side, setSide] = useState<Side>("student");
  return (
    <div className="safe-top flex flex-1 flex-col px-1 pt-3">
      <div className="flex items-center gap-2 pl-5 pr-3">
        <Segmented label="Account type" className="flex-1" value={side} onChange={setSide}
          options={[{ value: "student", label: "Student" }, { value: "organizer", label: "Organizer" }]} />
        <button onClick={closeAuth} aria-label="Close" className="pressable grid size-11 shrink-0 place-items-center rounded-full text-text-2 hover:bg-text/6">
          <X className="size-5" />
        </button>
      </div>
      {/* Plain CSS fade on switch. Swapping animated (motion) blocks inside the popup made its close
          animation wait forever, leaving an invisible layer that blocked taps after sign-in on phones. */}
      <div key={side} className="auth-fade">
        <SidePanel side={side} initialMode="signin" autoFocus onAuthed={onAuthed} />
      </div>
    </div>
  );
}

/** We know who this is: one panel, and a quiet link to switch with a short fade. Remounted on every open. */
function SinglePanel({ audience, mode, onAuthed }: { audience: Side; mode: Mode; onAuthed: (u: User, isNew: boolean) => void }) {
  const [side, setSide] = useState<Side>(audience);
  return (
    <div className="safe-top flex flex-1 flex-col pt-4 md:pt-0">
      <div key={side} className="auth-fade">
          <SidePanel side={side} initialMode={side === audience ? mode : "signin"} autoFocus onAuthed={onAuthed} />
          <p className="callout -mt-2 px-6 pb-8 text-text-2 md:px-8">
            {side === "student" ? "Are you an organizer? " : "Looking for events? "}
            <button
              type="button"
              onClick={() => setSide(side === "student" ? "organizer" : "student")}
              className="inline-flex min-h-11 items-center font-medium text-accent"
            >
              {side === "student" ? "Create events instead" : "Discover events instead"}
            </button>
          </p>
      </div>
    </div>
  );
}

type PanelMode = Mode | "forgot";

function SidePanel({ side, initialMode, autoFocus, onAuthed }: {
  side: Side;
  initialMode: Mode;
  autoFocus: boolean;
  onAuthed: (u: User, isNew: boolean) => void;
}) {
  const [mode, setMode] = useState<PanelMode>(initialMode);
  const s = SIDES[side];
  const Icon = s.icon;
  return (
    <section className="flex flex-col p-6 pb-8 md:p-8" aria-label={s.title} data-autofocus={autoFocus ? "" : undefined}>
      <span className={`grid size-11 place-items-center rounded-[14px] ${side === "student" ? "bg-success/15 text-success-text" : "bg-accent-soft text-accent"}`}>
        <Icon className="size-6" aria-hidden />
      </span>
      <h2 className="title-2 mt-4">{s.title}</h2>
      <p className="callout mt-1 text-text-2">{s.line}</p>
      {mode !== "forgot" && (
        <Segmented label={`${s.title}: sign in or sign up`} className="mt-5 w-full" value={mode} onChange={setMode}
          options={[{ value: "signin", label: "Sign in" }, { value: "signup", label: "Sign up" }]} />
      )}
      <div key={mode} className="auth-rise mt-5">
          {mode === "signin" && <SignInForm side={side} onForgot={() => setMode("forgot")} onAuthed={onAuthed} />}
          {mode === "signup" && (side === "student" ? <StudentSignUp onAuthed={onAuthed} /> : <OrganizerSignUp onAuthed={onAuthed} />)}
          {mode === "forgot" && <ForgotForm onBack={() => setMode("signin")} />}
      </div>
    </section>
  );
}

function FormShell({ onSubmit, error, children, submit, loading }: {
  onSubmit: (e: FormEvent) => void;
  error: string | null;
  children: ReactNode;
  submit: string;
  loading: boolean;
}) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate={false}>
      {children}
      {error && <p role="alert" className="callout text-danger-text">{error}</p>}
      <Button size="lg" full type="submit" loading={loading} className="mt-1">{submit}</Button>
    </form>
  );
}

function SignInForm({ side, onForgot, onAuthed }: { side: Side; onForgot: () => void; onAuthed: (u: User, isNew: boolean) => void }) {
  const signIn = useSignIn();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const id = (f: string) => `${side}-signin-${f}`;
  return (
    <>
      <FormShell
        submit="Sign in"
        loading={signIn.isPending}
        error={error}
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          signIn.mutate({ ...form, role: side }, {
            onSuccess: (u) => onAuthed(u, false),
            onError: (err) => setError(message(err, "Couldn't sign in. Check your connection and try again.")),
          });
        }}
      >
        <Field id={id("email")} label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field id={id("password")} label="Password" type="password" autoComplete="current-password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
      </FormShell>
      <button type="button" onClick={onForgot} className="mt-3 inline-flex min-h-11 items-center callout font-medium text-accent">Forgot password?</button>
    </>
  );
}

function StudentSignUp({ onAuthed }: { onAuthed: (u: User, isNew: boolean) => void }) {
  const register = useRegister();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  return (
    <FormShell
      submit="Create account"
      loading={register.isPending}
      error={error}
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        register.mutate(form, {
          onSuccess: (u) => onAuthed(u, true),
          onError: (err) => setError(message(err, "Couldn't create your account. Try again.")),
        });
      }}
    >
      <Field id="student-signup-name" label="Name" autoComplete="name" required maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      <Field id="student-signup-email" label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
      <Field id="student-signup-password" label="Password" type="password" autoComplete="new-password" required minLength={8} hint="At least 8 characters." value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
    </FormShell>
  );
}

function OrganizerSignUp({ onAuthed }: { onAuthed: (u: User, isNew: boolean) => void }) {
  const register = useRegisterOrganizer();
  const [form, setForm] = useState({ name: "", org_name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  return (
    <FormShell
      submit="Create organizer account"
      loading={register.isPending}
      error={error}
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        register.mutate(form, {
          onSuccess: (u) => onAuthed(u, true),
          onError: (err) => setError(message(err, "Couldn't create your account. Try again.")),
        });
      }}
    >
      <Field id="org-signup-name" label="Name" autoComplete="name" required maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      <Field id="org-signup-org" label="Organization or club" autoComplete="organization" required minLength={2} maxLength={160} value={form.org_name} onChange={(e) => setForm({ ...form, org_name: e.target.value })} />
      <Field id="org-signup-email" label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
      <Field id="org-signup-password" label="Password" type="password" autoComplete="new-password" required minLength={8} hint="At least 8 characters." value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
    </FormShell>
  );
}

function ForgotForm({ onBack }: { onBack: () => void }) {
  const forgot = useForgotPassword();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <div>
      <button type="button" onClick={onBack} className="-ml-1 mb-2 inline-flex min-h-11 items-center gap-1 callout font-medium text-accent">
        <ArrowLeft className="size-4" aria-hidden /> Back to sign in
      </button>
      <p className="headline">Reset your password</p>
      {forgot.isSuccess ? (
        <p className="callout mt-2 text-text-2">If {email} has a ShowUp account, a reset link is on its way. It works for 30 minutes.</p>
      ) : (
        <>
          <p className="callout mt-1 text-text-2">We'll email you a link.</p>
          <form
            className="mt-4 flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              setError(null);
              forgot.mutate(email, { onError: (err) => setError(message(err, "Couldn't send the email. Try again.")) });
            }}
          >
            <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            {error && <p role="alert" className="callout text-danger-text">{error}</p>}
            <Button size="lg" full type="submit" loading={forgot.isPending}>Send reset link</Button>
          </form>
        </>
      )}
    </div>
  );
}

/** After sign-in: close, then finish what the guest started (register, save, create...) without another tap. */
function useFinish() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const qc = useQueryClient();
  const toast = useToast();

  return async (user: User, isNew: boolean, intent: Intent | null) => {
    closeAuth();
    const student = user.role === "student";
    const wrongSide = (what: string) =>
      toast({ tone: "error", title: `${what} needs a ${student ? "organizer" : "student"} account`, body: "Sign out, then use the other side of the sign-in window." });
    try {
      if (intent?.kind === "register") {
        if (!student) return wrongSide("Registering");
        if (!pathname.startsWith(`/event/${intent.eventId}`)) navigate(`/event/${intent.eventId}`);
        const r = await api<Registration>(`/events/${intent.eventId}/register`, { method: "POST" });
        if (r.toast) toast({ tone: "success", title: r.toast.title, body: r.toast.body });
        await qc.invalidateQueries();
        return;
      }
      if (intent?.kind === "save") {
        if (!student) return wrongSide("Saving events");
        await api(`/events/${intent.eventId}/save`, { method: "POST" });
        toast({ tone: "success", title: "Saved" });
        await qc.invalidateQueries();
        return;
      }
      if (intent?.kind === "create_event") {
        if (student) return wrongSide("Creating events");
        navigate("/organizer/new");
        return;
      }
      if (intent?.kind === "navigate") {
        navigate(intent.to, { replace: true });
        return;
      }
      if (student && isNew) navigate("/welcome");
      else if (!pathname.startsWith("/event/")) navigate("/");
    } catch (e) {
      toast({ tone: "error", title: "Signed in, but that didn't go through", body: message(e, "Try again.") });
    }
  };
}
