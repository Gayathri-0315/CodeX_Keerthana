import { ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { ApiError } from "../lib/api";
import { useDemoSignIn, useMe, usePublicConfig, useSignIn } from "../lib/queries";
import type { Role } from "../lib/types";

export default function SignIn() {
  const { data: me } = useMe();
  const { data: config } = usePublicConfig();
  const signIn = useSignIn();
  const demo = useDemoSignIn();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);

  if (me) return <Navigate to="/" replace />;

  const fail = (err: unknown) => setError(err instanceof ApiError ? err.message : "Couldn't sign in. Try again.");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    signIn.mutate(form, { onSuccess: () => navigate("/"), onError: fail });
  };
  const demoAs = (role: Role) => demo.mutate(role, { onSuccess: () => navigate("/"), onError: fail });

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-5 safe-top">
      <div className="flex h-16 items-center">
        <Link to="/welcome" aria-label="Back" className="pressable -ml-2 grid size-11 place-items-center rounded-full text-accent">
          <ArrowLeft className="size-6" />
        </Link>
      </div>
      <Logo />
      <h1 className="title-1 mb-6 mt-6">Welcome back</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field label="Password" type="password" autoComplete="current-password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <p role="alert" className="callout text-danger-text">{error}</p>}
        <Button size="lg" full type="submit" loading={signIn.isPending} className="mt-2">Sign in</Button>
      </form>
      {config?.demo_mode && (
        <div className="mt-8 card p-4">
          <p className="footnote mb-2 font-medium text-text-2">Demo accounts (password demo1234)</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <Button variant="secondary" onClick={() => demoAs("student")} disabled={demo.isPending}>Demo student</Button>
            <Button variant="secondary" onClick={() => demoAs("organizer")} disabled={demo.isPending}>Demo organizer</Button>
            <Button variant="secondary" onClick={() => demoAs("admin")} disabled={demo.isPending}>Admin</Button>
          </div>
        </div>
      )}
    </div>
  );
}
