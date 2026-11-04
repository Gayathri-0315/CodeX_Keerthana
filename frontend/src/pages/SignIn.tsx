import { ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { ApiError } from "../lib/api";
import { useMe, useSignIn } from "../lib/queries";

export default function SignIn() {
  const { data: me } = useMe();
  const signIn = useSignIn();
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
      <Link to="/forgot" className="mt-4 inline-flex min-h-11 items-center self-center callout font-medium text-accent">
        Forgot password?
      </Link>
    </div>
  );
}
