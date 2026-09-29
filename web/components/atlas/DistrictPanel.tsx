import Link from "next/link";
import { Badge, Card, Spinner } from "@/components/ui";
import { formatNumber, toTitleCase } from "@/lib/format";

/** Side panel for the district clicked on the map. */
export function DistrictPanel({ district }: { district: any }) {
  if (!district) return <Card title="District profile"><p className="text-sm text-muted">Click any district on the map.</p></Card>;
  if (district.loading) return <Card title={district.name}><Spinner /></Card>;

  return (
    <Card title={`${toTitleCase(district.name)}, ${toTitleCase(district.state_name)}`}
      right={<Link href={`/districts/${district.district_lgd}`} className="text-sm">Full profile →</Link>}>
      <div className="space-y-3 text-sm">
        <div className="grid grid-cols-1 gap-1">
          {district.metrics.slice(0, 12).map((m: any) => (
            <div key={m.metric} className="flex justify-between gap-2 border-b border-line/60 py-1">
              <span className="text-muted">{m.name}</span>
              <span className="text-right tabular-nums">{formatNumber(m.value, 1)} <span className="text-xs text-muted">p{m.national_percentile}</span></span>
            </div>
          ))}
        </div>
        {district.conflicts.length > 0 && (
          <div>
            <div className="mb-1 font-medium">{district.conflicts.length} documented land conflicts</div>
            {district.conflicts.slice(0, 3).map((c: any) => (
              <a key={c.url} href={c.url} target="_blank" rel="noopener noreferrer" className="block truncate text-xs">{c.title}</a>
            ))}
          </div>
        )}
        {district.has_cadastral && <Badge tone="ok">Cadastral parcels available: tick the overlay and zoom in</Badge>}
      </div>
    </Card>
  );
}
