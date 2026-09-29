import { SignInLink } from "@/components/auth/SignInLink";
import type { ApiError } from "@/lib/api/client";

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiError;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
      {e.status === 401 ? (
        <>Sign in to use this. <SignInLink className="underline" /></>
      ) : e.status === 403 ? (
        <>Your role does not allow this: {e.message}</>
      ) : (
        <>{e.message ?? String(error)}</>
      )}
    </div>
  );
}
