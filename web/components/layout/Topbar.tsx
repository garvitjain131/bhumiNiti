import Link from "next/link";
import { useEffect, useState } from "react";
import { findNav } from "@/config/navigation";
import { useAuth } from "@/lib/auth/AuthProvider";
import { STRINGS } from "@/lib/i18n/strings";
import { useTheme } from "@/lib/theme/ThemeProvider";
import { Icon } from "./Icon";
import { UserMenu } from "./UserMenu";

/** Reading-progress line under the top bar, in the colour of the current section. */
function ScrollProgress({ color }: { color: string }) {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const update = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(window.scrollY / max, 1) : 0);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => { window.removeEventListener("scroll", update); window.removeEventListener("resize", update); };
  }, []);
  return (
    <div className="absolute inset-x-0 bottom-[-1px] h-[3px]" aria-hidden>
      <div className="h-full transition-[width] duration-150" style={{ width: `${Math.max(progress * 100, 12)}%`, background: color }} />
    </div>
  );
}

/** Fixed top bar: "bhumiNiti" (home link) | open page, command palette, language, theme and account. */
export function Topbar({ pathname, onOpenMobile, onOpenPalette }: { pathname: string; onOpenMobile: () => void; onOpenPalette: () => void }) {
  const { language, setLanguage } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const nav = findNav(pathname);
  const key = nav?.item.labelKey ?? (pathname.startsWith("/login") ? "signIn" : null);
  const pageName = key && pathname !== "/" ? STRINGS[language][key] : null;

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-[var(--topbar)] px-3 backdrop-blur md:px-6">
      <button type="button" onClick={onOpenMobile} aria-label="Open menu" aria-controls="sidebar"
        className="rounded-md p-1.5 text-muted hover:bg-subtle hover:text-ink md:hidden">
        <Icon name="menu" />
      </button>
      {/* fixed product name (home link) + the page that is open */}
      <div className="flex min-w-0 items-baseline gap-2.5">
        <Link href="/" title="Home" className="shrink-0 font-serif text-xl font-bold text-accent no-underline hover:opacity-85">
          bhumiNiti
        </Link>
        {pageName && (
          <>
            <span className="text-lg text-muted/60" aria-hidden>|</span>
            <span className="truncate font-serif text-lg font-bold text-ink">{pageName}</span>
          </>
        )}
      </div>

      <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
        <button type="button" onClick={onOpenPalette} aria-label="Search and jump (Ctrl+K)"
          className="flex items-center gap-2 rounded-md border border-line bg-field px-2.5 py-1 text-sm text-muted hover:bg-subtle hover:text-ink">
          <Icon name="search" className="h-4 w-4" />
          <span className="hidden lg:inline">{STRINGS[language].searchCommand}</span>
          <kbd className="hidden rounded-[3px] border border-line px-1 font-mono text-[10px] sm:inline">Ctrl+K</kbd>
        </button>
        <button type="button" onClick={() => setLanguage(language === "en" ? "hi" : "en")} aria-label="Switch language"
          title={language === "en" ? "हिन्दी में देखें" : "View in English"}
          className="rounded-md border border-line bg-field px-2 py-1 font-mono text-xs hover:bg-subtle">
          <span className={language === "en" ? "font-bold text-ink" : "text-muted"}>EN</span>
          <span className="text-muted"> / </span>
          <span className={language === "hi" ? "font-bold text-ink" : "text-muted"}>हिं</span>
        </button>
        <button type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          className="rounded-md border border-line bg-field p-1.5 text-muted hover:bg-subtle hover:text-ink">
          <Icon name={theme === "dark" ? "sun" : "moon"} className="h-4 w-4" />
        </button>
        <UserMenu />
      </div>
      <ScrollProgress color={nav?.section.color ?? "var(--accent)"} />
    </header>
  );
}
