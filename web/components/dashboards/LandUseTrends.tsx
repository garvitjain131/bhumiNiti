import { useState } from "react";
import EChart from "@/components/charts/EChart";
import { lineChartOption } from "@/components/charts/chartOptions";
import { StateFilter } from "@/components/dashboards/StateFilter";
import { Card, DataLabel, DataTable, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { toTitleCase } from "@/lib/format";

const pctSeries = (rows: any[]) => rows.map((r) => [r.year, r.pct] as [number, number]);

export default function LandUseTrends() {
  const [state, setState] = useState("");
  const { data } = useApi("/api/v1/dashboards/land-use", { state: state || undefined });
  return (
    <>
      <StateFilter value={state} onChange={setState} />
      {!data ? <Spinner /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={`Cropland and forest share, ${data.area} (MODIS, % of area)`} right={<DataLabel label="ESTIMATED" />}>
            <EChart option={lineChartOption([
              { name: "Cropland", data: pctSeries(data.cropland_share_modis) },
              { name: "Forest", data: pctSeries(data.forest_share_modis) },
            ], { yName: "%" })} />
          </Card>
          <Card title="Dynamic World 10 m: crops, built-up, trees (%)" right={<DataLabel label="ESTIMATED" />}>
            <EChart option={lineChartOption([
              { name: "Crops", data: pctSeries(data.cropland_share_dw) },
              { name: "Built-up", data: pctSeries(data.built_share_dw) },
              { name: "Trees", data: pctSeries(data.trees_share_dw) },
            ], { yName: "%" })} />
          </Card>
          <Card title="Built-up area km² (GHSL; 2025–2030 projected)">
            <EChart option={lineChartOption([
              { name: "Observed", data: data.built_up_km2_ghsl.filter((r: any) => r.year <= 2020).map((r: any) => [r.year, r.km2]) },
              { name: "Projected", data: data.built_up_km2_ghsl.filter((r: any) => r.year >= 2020).map((r: any) => [r.year, r.km2]), dashed: true },
            ], { yName: "km²" })} />
          </Card>
          <Card title="Largest cropland-share falls 2017–2025 (percentage points)">
            <DataTable rows={data.top_cropland_loss} columns={[
              { key: "name", label: "District", render: (r) => toTitleCase(r.name) },
              { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
              { key: "pp", label: "Δ pp", align: "right" },
            ]} />
          </Card>
        </div>
      )}
    </>
  );
}
