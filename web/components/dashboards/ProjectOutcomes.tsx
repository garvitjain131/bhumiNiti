import { KpiGrid } from "@/components/dashboards/KpiGrid";
import { Card, DataTable, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";

export default function ProjectOutcomes() {
  const { data } = useApi("/api/v1/dashboards/project-outcomes");
  if (!data) return <Spinner />;
  return (
    <>
      <KpiGrid kpis={data.kpis} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Platform pilots and reported outcomes">
          <DataTable rows={data.pilot_outcomes} empty="No outcomes reported yet." columns={[
            { key: "pilot", label: "Pilot" },
            { key: "indicator", label: "Indicator" },
            { key: "baseline", label: "Before", align: "right" },
            { key: "result", label: "After", align: "right" },
            { key: "unit", label: "Unit" },
          ]} />
          <p className="mt-2 text-xs text-muted">Outcomes enter the evidence base after review (Innovation Portal).</p>
        </Card>
        <Card title="States furthest behind on ULPIN (DILRMP)">
          <DataTable rows={data.dilrmp_progress} columns={[
            { key: "state", label: "State" },
            { key: "maps_digitised_pct", label: "Maps %", align: "right" },
            { key: "georef_pct", label: "Geo-ref %", align: "right" },
            { key: "ulpin_pct", label: "ULPIN %", align: "right" },
          ]} />
        </Card>
      </div>
    </>
  );
}
