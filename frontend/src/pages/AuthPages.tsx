import { ArrowLeft } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { useToast } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { useForgotPassword, useResetPassword } from "../lib/queries";

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

export function ForgotPage() {
  const forgot = useForgotPassword();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (forgot.isSuccess) {
    return (
      <AuthLayout title="Check your email" subtitle={`If ${email} has a ShowUp account, a reset link is on its way. It works for 30 minutes.`} back="/">
        <Link to="/signin" className="callout font-medium text-accent">Back to sign in</Link>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we'll send you a link." back="/">
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
    <AuthLayout title="Choose a new password" subtitle="You'll be signed out everywhere else." back="/">
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
