import { useState } from "react";
import { DistrictLink } from "@/components/dashboards/DistrictLink";
import { Button, Card, DataTable, ErrorAlert, inputClass } from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatNumber, toTitleCase } from "@/lib/format";

/** Combine district metrics with high/low rules, e.g. built-up growth high and cropland falling. */
export function SpatialQueryCard() {
  const [rules, setRules] = useState("built_growth_2000_2020:high,crops_change_2017_2025:low");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);

  async function runQuery() {
    setError(null);
    try {
      setResult(await api.get("/api/v1/geo/query", { rules }));
    } catch (e) {
      setError(e);
    }
  }

  return (
    <Card title="Ask a spatial question" className="mt-4">
      <p className="mb-2 text-sm text-muted">
        Combine metrics, e.g. <i>where is built-up growth high and cropland falling?</i> Each rule takes the top or bottom 25% of districts.
      </p>
      <div className="flex gap-2">
        <input className={inputClass} value={rules} onChange={(e) => setRules(e.target.value)} aria-label="rules" />
        <Button onClick={runQuery}>Find districts</Button>
      </div>
      <ErrorAlert error={error} />
      {result && (
        <div className="mt-3">
          <p className="mb-2 text-sm">{result.count} districts match ({result.method}).</p>
          <DataTable rows={result.districts.slice(0, 25)} columns={[
            { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
            { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
            ...Object.keys(result.rules).map((k) => ({
              key: k, label: k.replace(/_/g, " "), align: "right" as const, render: (r: any) => formatNumber(r[k], 1),
            })),
          ]} />
        </div>
      )}
    </Card>
  );
}
