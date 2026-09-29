/** Tab bar; TabbedPage keeps the active tab in the URL. The base line is an inset shadow, so nothing overflows
 *  vertically and no stray scrollbar appears when the tabs scroll sideways on narrow screens. */
export function Tabs({ tabs, value, onChange }: {
  tabs: { id: string; label: string }[]; value: string; onChange: (id: string) => void;
}) {
  return (
    <div className="mb-5 flex gap-1 overflow-x-auto overflow-y-hidden shadow-[inset_0_-1px_0_var(--line)]" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`shrink-0 border-b-2 px-3 py-2 text-sm transition-colors ${
            value === t.id ? "border-accent font-semibold text-ink" : "border-transparent text-muted hover:border-line hover:text-ink"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
