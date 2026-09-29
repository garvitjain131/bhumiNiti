import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";
import { AuthError, AuthLayout } from "@/components/auth/AuthLayout";
import { PasswordField } from "@/components/auth/PasswordField";
import { Button, inputClass } from "@/components/ui";
import type { ApiError } from "@/lib/api/client";
import { ROLE_LABELS, useAuth } from "@/lib/auth/AuthProvider";
import { authHref, safeNext } from "@/lib/auth/redirect";

function signInError(e: unknown): string {
  const err = e as ApiError;
  if (err?.status === 401) return "The email or password is incorrect.";
  if (err?.status === 429) return "Too many attempts. Wait a minute, then try again.";
  if (err?.status === 422) return "Enter a valid email address.";
  if (err?.status) return err.message;
  return "Could not reach the server. Check that the backend is running, then try again.";
}

export default function SignInPage() {
  const { login, logout, user, ready } = useAuth();
  const router = useRouter();
  const next = safeNext(router.query.next);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.replace(next);
    } catch (x) {
      setError(signInError(x));
      setBusy(false);
    }
  }

  if (ready && user.role !== "public" && !busy) {
    return (
      <AuthLayout title="Sign in">
        <h1 className="text-[26px] font-bold">You are signed in</h1>
        <p className="mt-2 text-sm text-muted">
          As <b className="text-ink">{user.name}</b> ({ROLE_LABELS[user.role] ?? user.role}{user.institution ? `, ${user.institution}` : ""}).
        </p>
        <div className="mt-6 flex gap-2">
          <Link href={next} className="flex-1 rounded-[4px] bg-accent-solid px-3.5 py-2 text-center text-sm font-medium text-white no-underline hover:brightness-110">
            Continue
          </Link>
          <Button variant="ghost" onClick={logout}>Sign out</Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Sign in">
      <h1 className="text-[26px] font-bold">Sign in</h1>
      <p className="mt-1.5 text-sm text-muted">Use your bhumiNiti account.</p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        {error && <AuthError message={error} />}
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium">Email</label>
          <input id="email" type="email" required autoFocus autoComplete="username" value={email}
            onChange={(e) => setEmail(e.target.value)} className={`${inputClass} py-2`} placeholder="name@organisation.gov.in" />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium">Password</label>
          <PasswordField id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </div>
        <Button type="submit" disabled={busy} className="w-full py-2">{busy ? "Signing in…" : "Sign in"}</Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted">
        New researcher? <Link href={authHref("/register", next)} className="font-medium">Create an account</Link>
      </p>
      <div className="mt-6 border-t border-line pt-4 text-xs leading-relaxed text-muted">
        Forgot your password, or need an official, reviewer or administrator account? Contact your platform administrator.
        {process.env.NODE_ENV !== "production" && <> Local demo accounts are listed in <code>db/demo_accounts.txt</code>.</>}
      </div>
    </AuthLayout>
  );
}
