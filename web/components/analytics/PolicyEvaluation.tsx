import { useState } from "react";
import { Button, Card, DataLabel, ErrorAlert, FormField, inputClass } from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";

export default function PolicyEvaluation() {
  const [form, setForm] = useState({ treatment: "ulpin_pct>=90", outcome: "dw_built", pre: "2017-2019", post: "2023-2025" });
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function runEvaluation() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.get("/api/v1/analytics/evaluate", form));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card title="Did a reform work? (difference-in-differences)">
        <div className="space-y-3">
          <FormField label="Treatment (DILRMP state status)" hint="ulpin_pct, georef_pct, maps_digitised_pct or ror_pct with >= or <=">
            <input className={inputClass} value={form.treatment} onChange={(e) => setForm({ ...form, treatment: e.target.value })} />
          </FormField>
          <FormField label="Outcome indicator">
            <input className={inputClass} value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })} />
          </FormField>
          <div className="grid grid-cols-2 gap-2">
            <FormField label="Before"><input className={inputClass} value={form.pre} onChange={(e) => setForm({ ...form, pre: e.target.value })} /></FormField>
            <FormField label="After"><input className={inputClass} value={form.post} onChange={(e) => setForm({ ...form, post: e.target.value })} /></FormField>
          </div>
          <Button onClick={runEvaluation} disabled={busy}>{busy ? "Running…" : "Run evaluation"}</Button>
        </div>
      </Card>
      <div>
        <ErrorAlert error={error} />
        {result && (
          <Card title="Result" right={<DataLabel label="CORRELATIONAL" />}>
            <div className="grid gap-3 text-sm md:grid-cols-3">
              <div>Treated districts: <b>{result.treated_districts}</b> ({result.treated_states.length} states)</div>
              <div>Control districts: <b>{result.control_districts}</b></div>
              <div>Change treated {formatNumber(result.change_treated, 4)} vs control {formatNumber(result.change_control, 4)}</div>
            </div>
            <p className="mt-3 text-lg">
              DiD estimate: <b>{formatNumber(result.did_estimate, 4)}</b> (95% state-bootstrap CI {formatNumber(result.ci95_state_bootstrap[0], 4)} to{" "}
              {formatNumber(result.ci95_state_bootstrap[1], 4)}) — {result.significant_at_5pct ? "different from zero" : "not distinguishable from zero"}.
            </p>
            <ul className="mt-2 list-disc pl-5 text-sm text-muted">{result.caveats.map((c: string) => <li key={c}>{c}</li>)}</ul>
          </Card>
        )}
      </div>
    </div>
  );
}
