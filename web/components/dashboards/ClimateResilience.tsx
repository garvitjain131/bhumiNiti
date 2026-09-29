import Link from "next/link";
import { useState } from "react";
import EChart from "@/components/charts/EChart";
import { barChartOption, lineChartOption } from "@/components/charts/chartOptions";
import { DistrictLink } from "@/components/dashboards/DistrictLink";
import { StateFilter } from "@/components/dashboards/StateFilter";
import { Card, DataLabel, DataTable, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { formatNumber, toTitleCase } from "@/lib/format";

export default function ClimateResilience() {
  const [state, setState] = useState("");
  const { data } = useApi("/api/v1/dashboards/climate", { state: state || undefined });
  return (
    <>
      <StateFilter value={state} onChange={setState} />
      {!data ? <Spinner /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={`Annual rainfall, ${data.area} (mm)`} right={<DataLabel label="ESTIMATED" />}>
            <EChart option={{
              ...barChartOption(data.rainfall_mm.map((r: any) => String(r.year)), data.rainfall_mm.map((r: any) => r.mm)),
              grid: { left: 48, right: 16, top: 24, bottom: 40 },
            }} />
          </Card>
          <Card title="Tree cover (%)" right={<DataLabel label="ESTIMATED" />}>
            <EChart option={lineChartOption([{ name: "Tree cover", data: data.tree_cover_pct.map((r: any) => [r.year, r.pct]) }], { yName: "%" })} />
          </Card>
          <Card title="Highest climate-risk districts (screening index 0–100)">
            <DataTable rows={data.highest_risk_districts} columns={[
              { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
              { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
              { key: "index", label: "Index", align: "right" },
            ]} />
            <p className="mt-2 text-xs text-muted">{data.method}</p>
          </Card>
          <Card title="Hazard exposure and DoLR Wastelands Atlas">
            <DataTable rows={data.exposure} columns={[
              { key: "name", label: "Hazard" },
              { key: "districts_exposed", label: "Districts", align: "right" },
              { key: "total", label: "Events", align: "right", render: (r) => formatNumber(r.total) },
            ]} />
            <div className="mt-3 text-sm font-medium">Wastelands Atlas of India 2019 (state chapters)</div>
            <div className="mt-1 flex flex-wrap gap-1 text-xs">
              {data.wastelands_atlas.map((a: any) => (
                <Link key={a.evidence_id} href={`/evidence/${encodeURIComponent(a.evidence_id)}`} className="rounded border border-line px-2 py-0.5">
                  {a.title.replace("Wastelands Atlas 2019: ", "")}
                </Link>
              ))}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
