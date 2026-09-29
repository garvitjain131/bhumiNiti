import { useRouter } from "next/router";
import { useEffect, useMemo, useRef, useState } from "react";
import { MAIN_NAV, PAGE_SHORTCUTS } from "@/config/navigation";
import { useAuth } from "@/lib/auth/AuthProvider";
import { STRINGS } from "@/lib/i18n/strings";
import { Icon } from "./Icon";

type Entry = { href: string; label: string; hint: string };

/** Ctrl+K: jump to any page or tab, or send the typed text to search or the research assistant. */
export function CommandPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const { hasRole, language } = useAuth();
  const t = STRINGS[language];
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);

  const entries = useMemo<Entry[]>(() => {
    const pages: Entry[] = [
      ...MAIN_NAV.filter((n) => !n.minimumRole || hasRole(n.minimumRole)).map((n) => ({ href: n.href, label: t[n.labelKey], hint: "Page" })),
      ...PAGE_SHORTCUTS.map((s) => ({ href: s.href, label: s.label, hint: t[s.section] })),
    ];
    const q = query.trim().toLowerCase();
    const matches = q ? pages.filter((p) => p.label.toLowerCase().includes(q)) : pages.slice(0, 11);
    if (q.length > 2) {
      matches.push(
        { href: `/assistant?q=${encodeURIComponent(query.trim())}`, label: `Ask the research assistant: “${query.trim()}”`, hint: "Ask" },
        { href: `/search?q=${encodeURIComponent(query.trim())}`, label: `Search the repository for “${query.trim()}”`, hint: "Search" },
      );
    }
    return matches;
  }, [query, hasRole, t]);

  function go(entry?: Entry) {
    if (!entry) return;
    onClose();
    router.push(entry.href);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") { e.preventDefault(); setSelected((s) => Math.min(s + 1, entries.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); go(entries[selected]); }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/40 px-4 pt-[12vh]" onMouseDown={onClose}>
      <div role="dialog" aria-label="Command palette" className="w-full max-w-xl overflow-hidden rounded-md border border-line bg-panel shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Icon name="search" className="h-4 w-4 text-muted" />
          <input ref={input} value={query} onChange={(e) => { setQuery(e.target.value); setSelected(0); }} onKeyDown={onKeyDown}
            placeholder={t.commandPlaceholder} aria-label="Command"
            className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-muted" />
          <kbd className="rounded-[3px] border border-line px-1.5 font-mono text-[10px] text-muted">Esc</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto py-1" role="listbox">
          {entries.length === 0 && <li className="px-4 py-3 text-sm text-muted">No page matches.</li>}
          {entries.map((e, i) => (
            <li key={e.href} role="option" aria-selected={i === selected}>
              <button type="button" onMouseEnter={() => setSelected(i)} onClick={() => go(e)}
                className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm ${i === selected ? "bg-accent-soft text-ink" : "text-ink"}`}>
                <span className="truncate">{e.label}</span>
                <span className="shrink-0 text-[11px] uppercase tracking-wider text-muted">{e.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
