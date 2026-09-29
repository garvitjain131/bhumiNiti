import Head from "next/head";
import { useRouter } from "next/router";
import { findNav } from "@/config/navigation";
import { STRINGS } from "@/lib/i18n/strings";

/** Page frame: serif title, subtitle and actions on the dotted header band. Section names appear only in the sidebar. */
export function PageContainer({ title, subtitle, actions, children }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode;
}) {
  const { pathname } = useRouter();
  const nav = findNav(pathname);
  const tabTitle = typeof title === "string" ? title : nav ? STRINGS.en[nav.item.labelKey] : "Land Policy Intelligence Platform";

  return (
    <div>
      <Head><title>{`${tabTitle} · Land Policy Intelligence Platform`}</title></Head>
      <header className="page-band border-b border-line">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-end justify-between gap-4 px-4 pb-6 pt-7 md:px-8">
          <div className="min-w-0 max-w-3xl">
            <h1 className="text-[28px] font-bold leading-tight md:text-[34px]">{title}</h1>
            {subtitle && <div className="mt-2 text-[15px] leading-relaxed text-muted">{subtitle}</div>}
          </div>
          {actions}
        </div>
      </header>
      <div className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8">{children}</div>
    </div>
  );
}
