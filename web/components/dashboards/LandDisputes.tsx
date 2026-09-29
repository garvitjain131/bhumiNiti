import EChart from "@/components/charts/EChart";
import { barChartOption, lineChartOption } from "@/components/charts/chartOptions";
import { KpiGrid } from "@/components/dashboards/KpiGrid";
import { Card, DataTable, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { toTitleCase } from "@/lib/format";

export default function LandDisputes() {
  const { data } = useApi("/api/v1/dashboards/disputes");
  if (!data) return <Spinner />;
  return (
    <>
      <KpiGrid kpis={data.kpis} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Conflicts by sector">
          <EChart option={barChartOption(data.by_sector.map((r: any) => r.key), data.by_sector.map((r: any) => r.n), { horizontal: true })} />
        </Card>
        <Card title="New conflicts by start year">
          <EChart option={lineChartOption([{ name: "Conflicts", data: data.by_start_year.map((r: any) => [r.year, r.n]) }])} />
        </Card>
        <Card title="Conflicts by state">
          <EChart height={520} option={barChartOption(data.by_state.map((r: any) => toTitleCase(r.key)), data.by_state.map((r: any) => r.n), { horizontal: true })} />
        </Card>
        <div className="space-y-4">
          <Card title="Leading causes">
            <DataTable rows={data.by_cause} columns={[{ key: "key", label: "Cause" }, { key: "n", label: "Conflicts", align: "right" }]} />
          </Card>
          <Card title="Type of land">
            <DataTable rows={data.by_land_type} columns={[{ key: "key", label: "Land type" }, { key: "n", label: "Conflicts", align: "right" }]} />
          </Card>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">{data.note} Source: Land Conflict Watch.</p>
    </>
  );
}
