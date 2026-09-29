import Link from "next/link";
import { useState } from "react";
import EChart from "@/components/charts/EChart";
import { Button, Card, DataTable, ErrorAlert, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatNumber, toTitleCase } from "@/lib/format";

export default function GapRadar() {
  const { data: gaps, reload } = useApi("/api/v1/gaps/states");
  const { hasRole } = useAuth();
  const [draftedCall, setDraftedCall] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  if (!gaps) return <Spinner />;

  async function draftCall(state: string) {
    setError(null);
    try {
      setDraftedCall(await api.post("/api/v1/gaps/to-call", { state, theme: "land_disputes", kind: "institutional_grant" }));
      reload();
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Research Gap Radar: need vs evidence">
        <p className="mb-2 text-sm text-muted">
          Need = conflicts per person (Land Conflict Watch) and parcels without a ULPIN (DILRMP-MIS). Evidence = land studies mentioning
          the state, including reviewed platform contributions. Top-left = high need, little research.
        </p>
        <EChart height={380} option={{
          tooltip: { trigger: "item", formatter: (p: any) => `${toTitleCase(p.data[2])}<br/>need ${p.data[1]} · ${p.data[0]} studies · gap ${p.data[3]}` },
          xAxis: { type: "log", name: "Research items (log)", min: 1 },
          yAxis: { type: "value", name: "Need index", min: 0, max: 1 },
          series: [{
            type: "scatter",
            data: gaps.map((r: any) => [Math.max(r.evidence_items, 1), r.need_index, r.state, r.gap_score]),
            symbolSize: (d: any) => 6 + d[3] * 30,
            label: { show: true, formatter: (p: any) => (p.data[3] > 0.2 ? toTitleCase(p.data[2]) : ""), position: "right", fontSize: 10 },
          }],
        }} />
      </Card>
      <ErrorAlert error={error} />
      {draftedCall && (
        <p className="rounded-md bg-accent-soft p-3 text-sm">
          Draft call created: <b>{draftedCall.title}</b>. Open it under <Link href="/innovation?tab=calls">Calls</Link> to review and publish.
        </p>
      )}
      <Card title="Highest gaps">
        <DataTable rows={gaps.slice(0, 20)} columns={[
          { key: "state", label: "State", render: (r) => toTitleCase(r.state) },
          { key: "conflicts", label: "Conflicts", align: "right" },
          { key: "conflicts_per_10m", label: "per 10M", align: "right" },
          { key: "ulpin_pct", label: "ULPIN %", align: "right", render: (r) => formatNumber(r.ulpin_pct) },
          { key: "evidence_items", label: "Studies", align: "right" },
          { key: "gap_score", label: "Gap", align: "right" },
          { key: "actions", label: "", render: (r) => hasRole("official") && (
            <Button variant="ghost" className="text-xs" onClick={() => draftCall(r.state)}>Draft a call</Button>
          ) },
        ]} />
      </Card>
    </div>
  );
}
