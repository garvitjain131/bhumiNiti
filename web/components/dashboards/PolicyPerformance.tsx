import EChart from "@/components/charts/EChart";
import { KpiGrid } from "@/components/dashboards/KpiGrid";
import { Card, DataLabel, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";

const PROGRESS_SERIES = [
  ["ror_pct", "RoR computerised"],
  ["maps_digitised_pct", "Maps digitised"],
  ["georef_pct", "Parcels geo-referenced"],
  ["ulpin_pct", "ULPIN assigned"],
];

export default function PolicyPerformance() {
  const { data } = useApi("/api/v1/dashboards/policy-performance");
  if (!data) return <Spinner />;
  const states = data.states.filter((r: any) => r.ulpin_pct !== null);
  return (
    <>
      <KpiGrid kpis={data.kpis} />
      <p className="mb-4 rounded-md bg-accent-soft p-3 text-sm">{data.insight}</p>
      <Card title="DILRMP progress by state (%)" right={<DataLabel label="OBSERVED" />}>
        <EChart height={640} option={{
          legend: { top: 0 }, tooltip: { trigger: "axis" }, grid: { left: 150, right: 20, top: 30, bottom: 20 },
          yAxis: { type: "category", data: states.map((r: any) => r.state), inverse: true },
          xAxis: { type: "value", max: 100 },
          series: PROGRESS_SERIES.map(([key, name]) => ({ type: "bar", name, data: states.map((r: any) => r[key]) })),
        }} />
        <p className="text-xs text-muted">Source: DILRMP-MIS physical progress reports (state level).</p>
      </Card>
    </>
  );
}
