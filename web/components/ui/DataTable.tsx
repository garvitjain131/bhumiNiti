export type Column<R = any> = { key: string; label: string; render?: (row: R) => React.ReactNode; align?: "right" };

export function DataTable<R = any>({ rows, columns, empty = "Nothing to show." }: {
  rows: R[] | null | undefined; columns: Column<R>[]; empty?: string;
}) {
  if (!rows?.length) return <p className="py-3 text-sm text-muted">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b-2 border-ink/70 text-left text-[11px] uppercase tracking-[0.08em] text-muted">
            {columns.map((c) => (
              <th key={c.key} className={`px-2 py-2 font-semibold ${c.align === "right" ? "text-right" : ""}`}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-line last:border-0 hover:bg-subtle/60">
              {columns.map((c) => (
                <td key={c.key} className={`px-2 py-1.5 align-top ${c.align === "right" ? "text-right font-mono text-[13px] tabular-nums" : ""}`}>
                  {c.render ? c.render(row) : ((row as any)[c.key] ?? "–")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
