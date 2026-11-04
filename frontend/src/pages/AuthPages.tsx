import { ArrowLeft, MailCheck } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { useToast } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { useForgotPassword, useMe, useResendVerification, useResetPassword, useVerifyEmail } from "../lib/queries";

const message = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

export function AuthLayout({ title, subtitle, back = "/", children }: { title: string; subtitle?: string; back?: string; children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-5 safe-top">
      <div className="flex h-16 items-center">
        <Link to={back} aria-label="Back" className="pressable -ml-2 grid size-11 place-items-center rounded-full text-accent">
          <ArrowLeft className="size-6" />
        </Link>
      </div>
      <Logo />
      <h1 className="title-1 mt-6">{title}</h1>
      {subtitle && <p className="body mt-2 text-text-2">{subtitle}</p>}
      <div className="mt-6">{children}</div>
    </div>
  );
}

/** The 6-digit code form. Used on /verify and in the verification sheet. */
export function VerifyCodeForm({ onDone }: { onDone?: () => void }) {
  const verify = useVerifyEmail();
  const resend = useResendVerification();
  const toast = useToast();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    verify.mutate({ code }, {
      onSuccess: () => {
        toast({ tone: "success", title: "Email verified" });
        onDone?.();
      },
      onError: (err) => setError(message(err, "Couldn't verify. Try again.")),
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field
        label="6-digit code"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="\d{6}"
        maxLength={6}
        required
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
        className="[&_input]:tnum [&_input]:tracking-[0.3em]"
      />
      {error && <p role="alert" className="callout text-danger-text">{error}</p>}
      <Button size="lg" full type="submit" loading={verify.isPending} disabled={code.length !== 6}>Verify email</Button>
      <Button
        variant="quiet"
        full
        type="button"
        loading={resend.isPending}
        onClick={() =>
          resend.mutate(undefined, {
            onSuccess: () => toast({ tone: "success", title: "New code sent", body: "Check your inbox (and spam folder)." }),
            onError: (err) => toast({ tone: "error", title: "Couldn't send", body: message(err, "Try again in a few minutes.") }),
          })
        }
      >
        Send a new code
      </Button>
    </form>
  );
}

/** /verify: with ?token= from the email link it verifies at once; otherwise it asks for the code. */
export function VerifyPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const { data: me, isPending } = useMe();
  const verify = useVerifyEmail();
  const navigate = useNavigate();
  const started = useRef(false);

  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      verify.mutate({ token });
    }
  }, [token, verify]);

  if (token) {
    return (
      <AuthLayout title={verify.isSuccess ? "Email verified" : verify.isError ? "That link didn't work" : "Verifying…"}
        subtitle={verify.isSuccess ? "You can register for events now." : verify.isError ? message(verify.error, "") : undefined}>
        {verify.isSuccess && <Button size="lg" full onClick={() => navigate("/")}>Continue</Button>}
        {verify.isError && <Button size="lg" full variant="secondary" onClick={() => navigate("/signin")}>Sign in</Button>}
      </AuthLayout>
    );
  }
  if (isPending) return <div className="min-h-dvh" />;
  if (!me) return <Navigate to="/signin" replace />;
  if (me.email_verified) return <Navigate to="/" replace />;
  return (
    <AuthLayout title="Check your email" subtitle={`We sent a 6-digit code to ${me.email}.`}>
      <div className="mb-6 grid size-14 place-items-center rounded-[16px] bg-accent-soft text-accent">
        <MailCheck className="size-7" aria-hidden />
      </div>
      <VerifyCodeForm onDone={() => navigate("/")} />
    </AuthLayout>
  );
}

export function ForgotPage() {
  const forgot = useForgotPassword();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (forgot.isSuccess) {
    return (
      <AuthLayout title="Check your email" subtitle={`If ${email} has a ShowUp account, a reset link is on its way. It works for 30 minutes.`} back="/signin">
        <Link to="/signin" className="callout font-medium text-accent">Back to sign in</Link>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we'll send you a link." back="/signin">
      <form
        className="flex flex-col gap-4"
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
    </AuthLayout>
  );
}

export function ResetPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const reset = useResetPassword();
  const navigate = useNavigate();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!token) return <Navigate to="/forgot" replace />;
  return (
    <AuthLayout title="Choose a new password" subtitle="You'll be signed out everywhere else." back="/signin">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          reset.mutate({ token, password }, {
            onSuccess: () => {
              toast({ tone: "success", title: "Password changed" });
              navigate("/", { replace: true });
            },
            onError: (err) => setError(message(err, "Couldn't change the password. Try again.")),
          });
        }}
      >
        <Field label="New password" type="password" autoComplete="new-password" minLength={8} required hint="At least 8 characters."
          value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p role="alert" className="callout text-danger-text">{error}</p>}
        <Button size="lg" full type="submit" loading={reset.isPending}>Save password</Button>
      </form>
    </AuthLayout>
  );
}
