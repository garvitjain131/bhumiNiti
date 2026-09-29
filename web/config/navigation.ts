import type { IconName } from "@/components/layout/Icon";
import type { StringKey } from "@/lib/i18n/strings";

export type NavItem = { href: string; labelKey: StringKey; icon: IconName; minimumRole?: string };
export type NavSection = { labelKey: StringKey; color: string; items: NavItem[] };

/** Sidebar navigation, grouped like strata: each section has its own colour. One entry per file in pages/. */
export const NAV_SECTIONS: NavSection[] = [
  { labelKey: "secStart", color: "var(--sec-overview)", items: [
    { href: "/", labelKey: "overview", icon: "home" },
  ] },
  { labelKey: "secDiscover", color: "var(--sec-discover)", items: [
    { href: "/search", labelKey: "search", icon: "search" },
    { href: "/assistant", labelKey: "assistant", icon: "assistant" },
  ] },
  { labelKey: "secExplore", color: "var(--sec-explore)", items: [
    { href: "/atlas", labelKey: "atlas", icon: "map" },
    { href: "/dashboards", labelKey: "dashboards", icon: "dashboard" },
    { href: "/analytics", labelKey: "analytics", icon: "chart" },
  ] },
  { labelKey: "secDecide", color: "var(--sec-decide)", items: [
    { href: "/policy-lab", labelKey: "policyLab", icon: "flask" },
    { href: "/workspaces", labelKey: "workspaces", icon: "users", minimumRole: "researcher" },
  ] },
  { labelKey: "secFund", color: "var(--sec-fund)", items: [
    { href: "/innovation", labelKey: "innovation", icon: "bulb" },
  ] },
  { labelKey: "secGovern", color: "var(--sec-govern)", items: [
    { href: "/data", labelKey: "data", icon: "database" },
    { href: "/admin", labelKey: "admin", icon: "shield", minimumRole: "official" },
  ] },
];

export const MAIN_NAV: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

/** Pages that belong to a sidebar entry without being under its URL. */
export const NAV_ALIASES: Record<string, string> = { "/calls": "/innovation", "/districts": "/atlas", "/evidence": "/search" };

/** The sidebar entry (and its section) that a path belongs to. */
export function findNav(pathname: string): { item: NavItem; section: NavSection } | null {
  const isUnder = (base: string) => pathname === base || pathname.startsWith(base + "/");
  const target = Object.entries(NAV_ALIASES).find(([alias]) => isUnder(alias))?.[1];
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      if (item.href === "/" ? pathname === "/" : target === item.href || isUnder(item.href)) return { item, section };
    }
  }
  return null;
}

/** Deep links offered by the command palette (Ctrl+K) in addition to the sidebar pages. */
export const PAGE_SHORTCUTS: { href: string; label: string; section: StringKey }[] = [
  { href: "/dashboards?tab=research", label: "Dashboards · Research outputs", section: "secExplore" },
  { href: "/dashboards?tab=policy-performance", label: "Dashboards · Policy performance", section: "secExplore" },
  { href: "/dashboards?tab=land-use", label: "Dashboards · Land-use trends", section: "secExplore" },
  { href: "/dashboards?tab=climate-resilience", label: "Dashboards · Climate resilience", section: "secExplore" },
  { href: "/dashboards?tab=land-disputes", label: "Dashboards · Land disputes", section: "secExplore" },
  { href: "/dashboards?tab=project-outcomes", label: "Dashboards · Project outcomes", section: "secExplore" },
  { href: "/dashboards?tab=geospatial", label: "Dashboards · Geospatial insights", section: "secExplore" },
  { href: "/analytics?tab=trends", label: "Analytics · Trends & forecasts", section: "secExplore" },
  { href: "/analytics?tab=policy-evaluation", label: "Analytics · Policy evaluation", section: "secExplore" },
  { href: "/analytics?tab=emerging-trends", label: "Analytics · Emerging trends & correlation", section: "secExplore" },
  { href: "/analytics?tab=model-registry", label: "Analytics · Model registry", section: "secExplore" },
  { href: "/innovation?tab=gap-radar", label: "Innovation · Gap Radar", section: "secFund" },
  { href: "/innovation?tab=calls", label: "Innovation · Calls", section: "secFund" },
  { href: "/innovation?tab=pilots", label: "Innovation · Pilot registry", section: "secFund" },
  { href: "/innovation?tab=contributions", label: "Innovation · Submit & review findings", section: "secFund" },
  { href: "/data?tab=catalog", label: "Data · Dataset catalogue", section: "secGovern" },
  { href: "/data?tab=apis", label: "Data · APIs & connectors", section: "secGovern" },
  { href: "/data?tab=land-records", label: "Data · Land records & anonymisation", section: "secGovern" },
];
