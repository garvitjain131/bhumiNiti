import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";
import { AuthError, AuthLayout } from "@/components/auth/AuthLayout";
import { PasswordField } from "@/components/auth/PasswordField";
import { Icon } from "@/components/layout/Icon";
import { Button, inputClass } from "@/components/ui";
import type { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { authHref, safeNext } from "@/lib/auth/redirect";

const MIN_PASSWORD = 10;

function Requirement({ met, children }: { met: boolean; children: React.ReactNode }) {
  return (
    <li className={`flex items-center gap-1.5 ${met ? "text-ok" : "text-muted"}`}>
      <Icon name={met ? "check" : "close"} className="h-3.5 w-3.5" /> {children}
    </li>
  );
}

export default function CreateAccountPage() {
  const { register, user, ready } = useAuth();
  const router = useRouter();
  const next = safeNext(router.query.next);
  const [form, setForm] = useState({ name: "", email: "", institution: "", password: "", confirm: "" });
  const [error, setError] = useState<React.ReactNode>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof form) => (value: string) => setForm({ ...form, [key]: value });

  const longEnough = form.password.length >= MIN_PASSWORD;
  const matches = form.password.length > 0 && form.password === form.confirm;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (form.name.trim().length < 2) return setError("Enter your full name.");
    if (!longEnough) return setError(`Use a password of at least ${MIN_PASSWORD} characters.`);
    if (!matches) return setError("The two passwords do not match.");
    setBusy(true);
    try {
      await register(form.email.trim(), form.name.trim(), form.password, form.institution.trim() || undefined);
      router.replace(next);
    } catch (x) {
      const err = x as ApiError;
      setError(err?.status === 409
        ? <>An account with this email already exists. <Link href={authHref("/login", next)} className="font-medium">Sign in instead</Link>.</>
        : err?.status === 422 ? "Check the details: enter a valid email address and your full name."
          : err?.status ? err.message : "Could not reach the server. Check that the backend is running, then try again.");
      setBusy(false);
    }
  }

  if (ready && user.role !== "public" && !busy) {
    return (
      <AuthLayout title="Create an account">
        <h1 className="text-[26px] font-bold">You already have an account</h1>
        <p className="mt-2 text-sm text-muted">You are signed in as <b className="text-ink">{user.name}</b>.</p>
        <Link href={next} className="mt-6 block rounded-[4px] bg-accent-solid px-3.5 py-2 text-center text-sm font-medium text-white no-underline hover:brightness-110">
          Continue
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Create an account">
      <h1 className="text-[26px] font-bold">Create a researcher account</h1>
      <p className="mt-1.5 text-sm text-muted">For researchers and students working on land governance.</p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        {error && <AuthError message={error} />}
        <div>
          <label htmlFor="name" className="mb-1 block text-sm font-medium">Full name</label>
          <input id="name" required autoFocus autoComplete="name" value={form.name} onChange={(e) => set("name")(e.target.value)}
            className={`${inputClass} py-2`} />
        </div>
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium">Email</label>
          <input id="email" type="email" required autoComplete="email" value={form.email} onChange={(e) => set("email")(e.target.value)}
            className={`${inputClass} py-2`} placeholder="name@university.ac.in" />
        </div>
        <div>
          <label htmlFor="institution" className="mb-1 block text-sm font-medium">
            Institution <span className="font-normal text-muted">(optional)</span>
          </label>
          <input id="institution" autoComplete="organization" value={form.institution} onChange={(e) => set("institution")(e.target.value)}
            className={`${inputClass} py-2`} />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium">Password</label>
          <PasswordField id="password" value={form.password} onChange={set("password")} autoComplete="new-password"
            minLength={MIN_PASSWORD} describedBy="password-rules" />
        </div>
        <div>
          <label htmlFor="confirm" className="mb-1 block text-sm font-medium">Confirm password</label>
          <PasswordField id="confirm" value={form.confirm} onChange={set("confirm")} autoComplete="new-password" describedBy="password-rules" />
          <ul id="password-rules" className="mt-2 space-y-0.5 text-xs">
            <Requirement met={longEnough}>At least {MIN_PASSWORD} characters</Requirement>
            <Requirement met={matches}>Both passwords match</Requirement>
          </ul>
        </div>
        <Button type="submit" disabled={busy} className="w-full py-2">{busy ? "Creating account…" : "Create account"}</Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted">
        Already have an account? <Link href={authHref("/login", next)} className="font-medium">Sign in</Link>
      </p>
      <p className="mt-6 border-t border-line pt-4 text-xs leading-relaxed text-muted">
        Self-registration creates a researcher account. Official, reviewer and administrator roles are granted by an administrator.
      </p>
    </AuthLayout>
  );
}
