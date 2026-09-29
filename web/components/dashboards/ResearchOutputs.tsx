import EChart from "@/components/charts/EChart";
import { barChartOption, lineChartOption } from "@/components/charts/chartOptions";
import { KpiGrid } from "@/components/dashboards/KpiGrid";
import { Card, DataTable, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { toTitleCase } from "@/lib/format";

export default function ResearchOutputs() {
  const { data } = useApi("/api/v1/dashboards/research");
  const { data: topics } = useApi("/api/v1/research/topic-trends");
  if (!data) return <Spinner />;
  return (
    <>
      <KpiGrid kpis={data.kpis} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Research papers per year">
          <EChart option={lineChartOption([{ name: "Papers", data: data.by_year.map((r: any) => [r.year, r.n]) }])} />
        </Card>
        <Card title="Repository by document type">
          <EChart option={barChartOption(data.by_type.map((r: any) => r.key), data.by_type.map((r: any) => r.n), { horizontal: true })} />
        </Card>
        <Card title="Research coverage by state (gaps are thin bars)">
          <EChart height={520} option={barChartOption(data.by_state.map((r: any) => r.key), data.by_state.map((r: any) => r.n), { horizontal: true })} />
        </Card>
        {topics && (
          <Card title="Rising and neglected themes (last 5 years vs previous 5)">
            <DataTable rows={topics.themes} columns={[
              { key: "theme", label: "Theme", render: (r) => toTitleCase(r.theme) },
              { key: "last_5y", label: "Last 5y", align: "right" },
              { key: "previous_5y", label: "Prev 5y", align: "right" },
              { key: "growth", label: "Growth", align: "right", render: (r) => r.growth === null ? "new" : `${Math.round(r.growth * 100)}%` },
            ]} />
          </Card>
        )}
      </div>
    </>
  );
}
