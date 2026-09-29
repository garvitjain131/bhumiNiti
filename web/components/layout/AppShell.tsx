import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const SIDEBAR_KEY = "lpip.sidebar";
/** Pages shown full-screen, without the sidebar and top bar. */
const STANDALONE_PAGES = new Set(["/login", "/register"]);

/** Fixed sidebar + fixed top bar around every page. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname, asPath } = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // the saved state was applied to <html data-sidebar> before paint (see _document.tsx)
  useEffect(() => setCollapsed(document.documentElement.dataset.sidebar === "collapsed"), []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((c) => {
      const next = !c;
      if (next) document.documentElement.dataset.sidebar = "collapsed";
      else delete document.documentElement.dataset.sidebar;
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? "collapsed" : "expanded");
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  useEffect(() => setMobileOpen(false), [asPath]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === "Escape") {
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (STANDALONE_PAGES.has(pathname)) return <>{children}</>;

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[70] focus:rounded-md focus:bg-panel focus:p-2">
        Skip to content
      </a>
      <Sidebar pathname={pathname} mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)}
        collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
      {mobileOpen && <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={() => setMobileOpen(false)} aria-hidden />}

      <div className="flex min-h-screen flex-col transition-[padding] duration-200 ease-out md:pl-[var(--sidebar-w)]">
        <Topbar pathname={pathname} onOpenMobile={() => setMobileOpen(true)} onOpenPalette={() => setPaletteOpen(true)} />
        <main id="main" className="flex-1">{children}</main>
        <footer className="border-t border-line px-4 py-4 text-xs text-muted md:px-8">
          Prototype for SIH26019 (DoLR). Public data from DILRMP-MIS, Survey of India / LGD, SHRUG, NFHS-5, Earth Engine datasets,
          OpenAlex, World Bank, Land Conflict Watch and others; see <Link href="/data">Data &amp; APIs</Link> for sources and
          licences. Land records shown are SYNTHETIC. Maps use Survey of India boundaries.
        </footer>
      </div>
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </div>
  );
}
