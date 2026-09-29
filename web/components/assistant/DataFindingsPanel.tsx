import { Fragment } from "react";
import { DistrictLink } from "@/components/dashboards/DistrictLink";
import { Card, DataLabel, DataTable } from "@/components/ui";
import { formatNumber, toTitleCase } from "@/lib/format";

function Provenance({ a }: { a: any }) {
  const fields: [string, string][] = [["Dataset", a.dataset], ["Indicator", `${a.indicator_name} (${a.indicator})`],
    ["Scope", a.scope], ["Period", a.period], ["Method", a.method]];
  return (
    <dl className="mb-2 grid grid-cols-[90px_1fr] gap-y-0.5 text-xs">
      {fields.map(([k, v]) => <Fragment key={k}><dt className="text-muted">{k}</dt><dd>{v}</dd></Fragment>)}
    </dl>
  );
}

/** SQL / Analytics output: every analysis with its dataset, indicator, scope, period, method and rows. */
export function DataFindingsPanel({ data }: { data: any }) {
  if (!data) return <p className="text-sm text-muted">This question did not need district data.</p>;
  if (!data.analyses.length) return <p className="text-sm text-muted">No platform indicator matched the question.</p>;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {data.analyses.map((a: any, i: number) => (
        <Card key={i} title={a.title} right={<DataLabel label={a.label} />}>
          <Provenance a={a} />
          {a.kind === "ranking" && (
            <DataTable rows={a.rows} columns={[
              { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
              { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
              { key: "value", label: a.unit || "Value", align: "right", render: (r) => formatNumber(r.value, 2) },
            ]} />
          )}
          {a.kind === "correlation" && (
            <p className="text-sm">Spearman ρ = <b>{formatNumber(a.result.spearman_rho, 3)}</b>, p = {formatNumber(a.result.p_value, 3)}, n = {a.result.n}. Association only.</p>
          )}
          {a.kind === "trend" && (
            <DataTable rows={a.rows.slice(-10)} columns={[
              { key: "year", label: "Year" },
              { key: "value", label: a.unit, align: "right", render: (r) => formatNumber(r.value, 3) },
            ]} />
          )}
        </Card>
      ))}
    </div>
  );
}
