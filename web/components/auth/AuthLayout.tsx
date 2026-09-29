import Head from "next/head";
import Link from "next/link";
import { Icon } from "@/components/layout/Icon";

const BENEFITS = [
  "Collaborative workspaces with versioned notes and review",
  "Apply to research grants, hackathons and pilots",
  "Save policy scenarios and export verifiable briefs",
  "Request access to controlled land-record data",
];

/** Full-screen sign-in / sign-up frame: navy brand panel on the left, the form on the right. */
export function AuthLayout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <Head><title>{`${title} · bhumiNiti`}</title></Head>

      <aside className="relative hidden flex-col justify-between overflow-hidden bg-sidebar px-12 py-10 text-sidebar-ink lg:flex"
        style={{ backgroundImage: "radial-gradient(circle, rgb(255 255 255 / 0.06) 1px, transparent 1.3px)", backgroundSize: "18px 18px" }}>
        <div className="tricolour absolute inset-x-0 top-0 h-[3px]" aria-hidden />
        <Link href="/" className="w-fit font-serif text-2xl font-bold text-white no-underline hover:opacity-90">bhumiNiti</Link>
        <div>
          <div className="eyebrow text-sidebar-muted">Research and policy intelligence for land governance</div>
          <h2 className="mt-3 max-w-md text-[36px] font-bold leading-tight text-white">Land Policy Intelligence</h2>
          <p className="mt-3 max-w-md text-[15px] leading-relaxed text-sidebar-ink/80">
            Evidence, district data and policy scenarios for land governance in one place, with the source behind every number.
          </p>
          <div className="mt-8 text-xs font-semibold uppercase tracking-[0.12em] text-sidebar-muted">With an account you can</div>
          <ul className="mt-3 space-y-2.5">
            {BENEFITS.map((b) => (
              <li key={b} className="flex items-start gap-3 text-[14px] text-sidebar-ink/90">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-[var(--flag-saffron)]">
                  <Icon name="check" className="h-3.5 w-3.5" />
                </span>
                {b}
              </li>
            ))}
          </ul>
        </div>
        <p className="max-w-md text-xs text-sidebar-muted">
          Public users can search the repository, read open documents and view dashboards without an account.
        </p>
      </aside>

      <main className="flex min-h-screen flex-col bg-bg">
        <div className="flex items-center justify-between px-6 py-5 md:px-10">
          <Link href="/" className="font-serif text-xl font-bold text-accent no-underline lg:invisible">bhumiNiti</Link>
          <Link href="/" className="flex items-center gap-1.5 text-sm text-muted no-underline hover:text-ink">
            <Icon name="arrowLeft" className="h-4 w-4" /> Back to the platform
          </Link>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-[420px] rounded-md border border-line bg-panel p-7 shadow-sm md:p-8">{children}</div>
        </div>
      </main>
    </div>
  );
}

/** Error message shown above an auth form. */
export function AuthError({ message }: { message: React.ReactNode }) {
  return (
    <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800" role="alert">{message}</div>
  );
}
