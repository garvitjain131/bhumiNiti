import Link from "next/link";
import { useRouter } from "next/router";
import { authHref } from "@/lib/auth/redirect";

/** "Sign in" link that returns the user to the page they are on. */
export function SignInLink({ children = "Sign in", className }: { children?: React.ReactNode; className?: string }) {
  const { asPath } = useRouter();
  return <Link href={authHref("/login", asPath)} className={className}>{children}</Link>;
}
