import Link from "next/link";
import { findNav, NAV_SECTIONS } from "@/config/navigation";
import { useAuth } from "@/lib/auth/AuthProvider";
import { STRINGS } from "@/lib/i18n/strings";
import { Icon } from "./Icon";

/**
 * Fixed navy sidebar. Desktop: full width or a collapsed icon rail (toggled by the button at the top or the
 * Collapse button at the bottom). Mobile: an off-canvas drawer opened from the top bar.
 */
export function Sidebar({ pathname, mobileOpen, onCloseMobile, collapsed, onToggleCollapsed }: {
  pathname: string; mobileOpen: boolean; onCloseMobile: () => void; collapsed: boolean; onToggleCollapsed: () => void;
}) {
  const { hasRole, language } = useAuth();
  const t = STRINGS[language];
  const active = findNav(pathname)?.item.href;

  return (
    <aside id="sidebar" aria-label="Sidebar"
      className={`fixed inset-y-0 left-0 z-50 flex w-[256px] flex-col bg-sidebar text-sidebar-ink transition-[transform,width] duration-200 ease-out md:w-[var(--sidebar-w)] md:translate-x-0 ${mobileOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"}`}>
      <div className="tricolour h-[3px] shrink-0" aria-hidden />
      <div className="flex h-[53px] shrink-0 items-center gap-2.5 border-b border-sidebar-line px-3 md:collapsed:justify-center md:collapsed:px-0">
        <button type="button" onClick={() => (mobileOpen ? onCloseMobile() : onToggleCollapsed())}
          aria-label={mobileOpen ? "Close menu" : collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-controls="sidebar"
          aria-expanded={mobileOpen || !collapsed}
          className="rounded-md p-1.5 text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-ink">
          <Icon name={mobileOpen ? "close" : "menu"} />
        </button>
      </div>

      <nav aria-label="Main" className="sidebar-scroll flex-1 overflow-y-auto px-2.5 py-4">
        {NAV_SECTIONS.map((section) => {
          const items = section.items.filter((i) => !i.minimumRole || hasRole(i.minimumRole));
          if (!items.length) return null;
          return (
            <div key={section.labelKey} className="mb-4">
              <div className="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-muted md:collapsed:hidden">
                {t[section.labelKey]}
              </div>
              <div className="mx-auto mb-2 hidden h-px w-6 bg-sidebar-line md:collapsed:block" aria-hidden />
              {items.map((item) => {
                const isActive = item.href === active;
                return (
                  <Link key={item.href} href={item.href} title={t[item.labelKey]} aria-current={isActive ? "page" : undefined}
                    className={`relative mb-0.5 flex items-center gap-3 rounded-md px-2.5 py-[7px] text-[13.5px] no-underline transition-colors md:collapsed:justify-center md:collapsed:px-0 ${
                      isActive ? "bg-sidebar-active font-semibold text-white" : "text-sidebar-ink/80 hover:bg-sidebar-hover hover:text-white"}`}>
                    {isActive && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r bg-[var(--flag-saffron)]" />}
                    <Icon name={item.icon} className="h-[17px] w-[17px]" />
                    <span className="truncate md:collapsed:hidden">{t[item.labelKey]}</span>
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      <div className="hidden shrink-0 border-t border-sidebar-line p-2.5 md:block">
        <button type="button" onClick={onToggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-sidebar-line py-1.5 text-xs text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-ink">
          <Icon name={collapsed ? "sidebarOpen" : "sidebar"} className="h-4 w-4" />
          <span className="collapsed:hidden">{t.collapse}</span>
        </button>
      </div>
    </aside>
  );
}
