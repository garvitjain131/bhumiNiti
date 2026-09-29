import { useState } from "react";
import EChart from "@/components/charts/EChart";
import { DistrictLink } from "@/components/dashboards/DistrictLink";
import { Card, DataLabel, DataTable, Spinner, inputClass } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { formatNumber, toTitleCase } from "@/lib/format";

function TopDistricts({ rows, valueLabel }: { rows: any[]; valueLabel: string }) {
  return (
    <DataTable rows={rows.slice(0, 8)} columns={[
      { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
      { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
      { key: "value", label: valueLabel, align: "right" },
    ]} />
  );
}

function CorrelationExplorer() {
  const [axes, setAxes] = useState({ x: "built_growth_2000_2020", y: "conflicts" });
  const { data: result } = useApi("/api/v1/analytics/correlate", axes);
  const { data: layers } = useApi("/api/v1/geo/layers");
  return (
    <Card title="Correlation explorer" right={<DataLabel label="CORRELATIONAL" />}>
      <div className="mb-2 grid gap-2 md:grid-cols-2">
        {(["x", "y"] as const).map((axis) => (
          <select key={axis} className={inputClass} value={axes[axis]} onChange={(e) => setAxes({ ...axes, [axis]: e.target.value })} aria-label={axis}>
            {(layers?.district_metrics ?? []).map((m: any) => <option key={m.metric} value={m.metric}>{m.name}</option>)}
          </select>
        ))}
      </div>
      {result && (
        <>
          <EChart height={320} option={{
            tooltip: { trigger: "item", formatter: (p: any) => `${p.data[2]}<br/>${formatNumber(p.data[0])} / ${formatNumber(p.data[1])}` },
            xAxis: { type: "value", name: result.x, scale: true },
            yAxis: { type: "value", name: result.y, scale: true },
            series: [{ type: "scatter", symbolSize: 5, data: result.points.map((p: any) => [p.x, p.y, toTitleCase(p.name)]) }],
          }} />
          <p className="text-sm">
            Spearman ρ = <b>{formatNumber(result.spearman_rho, 2)}</b> (n = {result.n}, p = {formatNumber(result.p_value, 3)}). {result.caveat}
          </p>
        </>
      )}
    </Card>
  );
}

export default function EmergingTrends() {
  const { data } = useApi("/api/v1/analytics/emerging");
  if (!data) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Fastest built-up growth (%)"><TopDistricts rows={data.fastest_built_up_growth} valueLabel="%" /></Card>
        <Card title="Largest cropland loss (pp)"><TopDistricts rows={data.largest_cropland_loss} valueLabel="pp" /></Card>
        <Card title="Fastest night-light growth (%)"><TopDistricts rows={data.fastest_night_light_growth} valueLabel="%" /></Card>
      </div>
      <Card title="Anomalies to investigate">
        <p className="mb-2 text-sm text-muted">{data.anomalies.indicator}; rule {data.anomalies.rule}. {data.anomalies.note}</p>
        <DataTable rows={data.anomalies.items} empty="No anomalies this year." columns={[
          { key: "name", label: "District", render: (r) => toTitleCase(r.name) },
          { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
          { key: "year", label: "Year" },
          { key: "change_pp", label: "Change pp", align: "right" },
          { key: "z_score", label: "z", align: "right" },
        ]} />
      </Card>
      <CorrelationExplorer />
    </div>
  );
}
