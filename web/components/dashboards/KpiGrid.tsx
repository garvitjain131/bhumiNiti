import { KpiCard } from "@/components/ui";
import { formatNumber } from "@/lib/format";

export type Kpi = { name: string; value: number | null; unit?: string; definition: string; source: string; label?: string };

/** Row of KPI cards; hovering a card shows its definition and source. */
export function KpiGrid({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
      {kpis.map((k) => (
        <KpiCard key={k.name} label={k.name} value={formatNumber(k.value, 2)} unit={k.unit}
          note={`${k.definition}. Source: ${k.source}`} dataLabel={k.label} />
      ))}
    </div>
  );
}
