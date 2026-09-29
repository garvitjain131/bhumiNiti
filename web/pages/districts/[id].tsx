import Link from "next/link";
import { useRouter } from "next/router";
import EChart from "@/components/charts/EChart";
import { lineChartOption } from "@/components/charts/chartOptions";
import { EvidenceListItem } from "@/components/evidence/EvidenceListItem";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card, DataLabel, DataTable, ErrorAlert, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { formatNumber, toTitleCase } from "@/lib/format";

/** Time series shown on the profile: [indicator, title, multiplier to display units]. */
const PROFILE_SERIES: [string, string, number][] = [
  ["dw_crops", "Cropland share (Dynamic World)", 100],
  ["dw_built", "Built-up share (Dynamic World)", 100],
  ["modis_cropland", "Cropland share (MODIS)", 100],
  ["ghsl_built_km2", "Built-up area km² (GHSL)", 1],
  ["viirs_ntl_mean", "Night-light radiance (VIIRS)", 1],
  ["chirps_rain_mm", "Annual rainfall mm (CHIRPS)", 1],
];

export default function DistrictProfilePage() {
  const router = useRouter();
  const lgd = typeof router.query.id === "string" ? router.query.id : null;
  const { data: district, error } = useApi(lgd && `/api/v1/geo/districts/${lgd}`);
  const { data: forecast } = useApi(lgd && "/api/v1/analytics/forecast", { indicator: "dw_built", district_lgd: lgd });

  if (error) return <PageContainer title="District"><ErrorAlert error={error} /></PageContainer>;
  if (!district) return <PageContainer title="District"><Spinner /></PageContainer>;
  const themes = [...new Set(district.metrics.map((m: any) => m.theme))] as string[];

  return (
    <PageContainer title={`${toTitleCase(district.name)}, ${toTitleCase(district.state_name)}`}
      subtitle={`LGD code ${district.district_lgd} · ${formatNumber(district.area_km2)} km² · national percentile shown as p0–p100`}
      actions={
        <span className="flex gap-3 text-sm">
          <Link href={`/assistant?q=${encodeURIComponent(`What does research say about land conflict in ${toTitleCase(district.state_name)}, and which districts in ${toTitleCase(district.state_name)} show the highest land conflict risk?`)}`}>
            Ask the research assistant
          </Link>
          <Link href="/atlas">← Atlas</Link>
        </span>
      }>
      <div className="grid gap-4 lg:grid-cols-3">
        {themes.map((theme) => (
          <Card key={theme} title={theme}>
            {district.metrics.filter((m: any) => m.theme === theme).map((m: any) => (
              <div key={m.metric} className="flex items-baseline justify-between gap-2 border-b border-line/60 py-1 text-sm" title={m.method}>
                <span className="text-muted">{m.name}</span>
                <span className="tabular-nums">
                  {formatNumber(m.value, 1)} <span className="text-xs text-muted">{m.unit} · p{m.national_percentile}</span> <DataLabel label={m.label} />
                </span>
              </div>
            ))}
          </Card>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {PROFILE_SERIES.map(([key, label, multiplier]) => district.series[key]?.length > 1 && (
          <Card key={key} title={label} right={<DataLabel label={district.series[key][0].label} />}>
            <EChart height={220} option={lineChartOption([{ name: label, data: district.series[key].map((r: any) => [r.year, r.value * multiplier]) }])} />
          </Card>
        ))}
        {forecast && (
          <Card title="Built-up share forecast to 2030" right={<DataLabel label="PREDICTED" />}>
            <EChart height={220} option={lineChartOption(
              [
                { name: "Observed", data: forecast.observed.map((r: any) => [r.year, r.value * 100]) },
                { name: "Forecast (P50)", data: forecast.forecast.map((r: any) => [r.year, r.p50 * 100]), dashed: true },
              ],
              { band: {
                name: "80% interval",
                lo: forecast.forecast.map((r: any) => [r.year, r.p10 * 100]),
                hi: forecast.forecast.map((r: any) => [r.year, r.p90 * 100]),
              } },
            )} />
            <p className="text-xs text-muted">{forecast.model.method}. Assumption: {forecast.model.assumption}.</p>
          </Card>
        )}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title={`Documented land conflicts (${district.conflicts.length})`}>
          <DataTable rows={district.conflicts} empty="No documented conflicts in this district." columns={[
            { key: "title", label: "Conflict", render: (r) => <a href={r.url} target="_blank" rel="noopener noreferrer">{r.title}</a> },
            { key: "year_started", label: "Since" },
            { key: "sector", label: "Sector" },
            { key: "people_affected", label: "People", align: "right", render: (r) => formatNumber(r.people_affected) },
          ]} />
        </Card>
        <Card title="Related evidence">
          {district.evidence.length
            ? district.evidence.map((r: any) => <EvidenceListItem key={r.evidence_id} item={r} />)
            : <p className="text-sm text-muted">No items mention this district by name.</p>}
        </Card>
        <Card title="Census 2011 (village directory aggregates)" className="lg:col-span-2">
          <DataTable rows={district.census} columns={[
            { key: "name", label: "Indicator" },
            { key: "value", label: "Value", align: "right", render: (r) => formatNumber(r.value) },
            { key: "unit", label: "Unit" },
          ]} />
        </Card>
      </div>
    </PageContainer>
  );
}
