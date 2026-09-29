import { DistrictLink } from "@/components/dashboards/DistrictLink";
import { Card, DataTable, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { formatNumber, toTitleCase } from "@/lib/format";

function DistrictRanking({ rows, valueKey, valueLabel }: { rows: any[]; valueKey: string; valueLabel: string }) {
  return (
    <DataTable rows={rows} columns={[
      { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
      { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
      { key: valueKey, label: valueLabel, align: "right", render: (r) => formatNumber(r[valueKey]) },
    ]} />
  );
}

export default function GeospatialInsights() {
  const { data } = useApi("/api/v1/dashboards/geospatial");
  if (!data) return <Spinner />;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="Conflict hotspots">
        <DistrictRanking rows={data.hotspots_conflict} valueKey="conflicts" valueLabel="Conflicts" />
      </Card>
      <Card title="Fastest urbanising (built-up growth 2000–2020, %)">
        <DistrictRanking rows={data.urbanising_fast} valueKey="pct" valueLabel="%" />
      </Card>
      <Card title="Pressure overlap">
        <DataTable rows={data.pressure_overlap} columns={[
          { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
          { key: "built_growth_pct", label: "Built +%", align: "right" },
          { key: "cropland_change_pp", label: "Crop Δpp", align: "right" },
          { key: "conflicts", label: "Conflicts", align: "right", render: (r) => r.conflicts ?? 0 },
        ]} />
        <p className="mt-2 text-xs text-muted">{data.method}</p>
      </Card>
    </div>
  );
}
