import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { PageContainer } from "@/components/layout/PageContainer";
import { AssumptionsTable, type CoefficientOverrides } from "@/components/policy-lab/AssumptionsTable";
import { ParameterInput } from "@/components/policy-lab/ParameterInput";
import { PolicyBriefCard } from "@/components/policy-lab/PolicyBriefCard";
import { ScenarioFanChart } from "@/components/policy-lab/ScenarioFanChart";
import { SensitivityTornado } from "@/components/policy-lab/SensitivityTornado";
import { Badge, Button, Card, DataLabel, DataTable, ErrorAlert, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { formatNumber, toTitleCase } from "@/lib/format";

const WORKFLOW_STEPS = [
  "Select policy problem", "Baseline", "Define intervention", "Set parameters", "Run scenario", "Inspect assumptions", "Compare", "Export brief",
];

/** Last value of a per-year series, or the value itself for a scalar. */
const finalValue = (v: number | number[]) => (Array.isArray(v) ? v.at(-1) : v);

export default function PolicyLabPage() {
  const router = useRouter();
  const { data: levers } = useApi("/api/v1/simulations/levers");
  const [loadedRun, setLoadedRun] = useState<any>(null);
  const [leverId, setLeverId] = useState("agri_conversion");
  const [params, setParams] = useState<any>({});
  const [overrides, setOverrides] = useState<CoefficientOverrides>({});
  const [run, setRun] = useState<any>(null);
  const [savedScenarios, setSavedScenarios] = useState<{ label: string; run: any }[]>([]);
  const [brief, setBrief] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  // ?run=<id> opens a stored scenario, e.g. one simulated by the research assistant's Digital Twin.
  useEffect(() => {
    if (!router.isReady || typeof router.query.run !== "string") return;
    api.get(`/api/v1/simulations/runs/${encodeURIComponent(router.query.run)}`)
      .then((r) => { setLoadedRun(r); setLeverId(r.lever); })
      .catch(setError);
  }, [router.isReady, router.query.run]);

  const lever = levers?.find((l: any) => l.id === leverId);
  useEffect(() => {
    if (!lever) return;
    const fromRun = loadedRun?.lever === lever.id ? loadedRun : null;
    const { coef_overrides: runOverrides, ...runParams } = fromRun?.params ?? {};
    setParams(fromRun ? runParams : { ...lever.default_params });
    setOverrides(runOverrides ?? {});
    setRun(fromRun);
    setSavedScenarios([]);
    setBrief(null);
  }, [lever, loadedRun]);

  async function runScenario() {
    setBusy(true);
    setError(null);
    setBrief(null);
    try {
      setRun(await api.post("/api/v1/simulations/run", { lever: leverId, params: { ...params, coef_overrides: overrides }, seed: 42 }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  function keepForComparison() {
    if (run) setSavedScenarios([...savedScenarios, { label: `Scenario ${String.fromCharCode(65 + savedScenarios.length)}`, run }].slice(-3));
  }

  async function reproduceRun() {
    const r = await api.post(`/api/v1/simulations/runs/${run.run_id}/reproduce`);
    alert(r.identical_results ? `Reproduced run #${run.run_id}: identical results (hash ${r.hash.slice(0, 12)}…).` : "Results differ.");
  }

  const impactKey = run ? Object.keys(run.impact)[0] : "";
  const impact = run?.impact[impactKey];

  return (
    <PageContainer title="Policy Lab"
      subtitle="Test a reform before rollout. Each lever is a transparent model: baseline from platform data, policy effects as graded coefficient ranges, 2,000 Monte Carlo draws. Results are scenarios, not predictions.">
      {loadedRun && run?.run_id === loadedRun.run_id && (
        <p className="mb-3 rounded-md bg-accent-soft p-2 text-sm">
          Opened stored scenario run #{loadedRun.run_id} ({loadedRun.lever_name}). Change parameters or coefficient ranges and run again,
          or export a verifiable brief for this run.
        </p>
      )}
      <ol className="mb-4 flex flex-wrap gap-1 text-xs">
        {WORKFLOW_STEPS.map((s, i) => <li key={s} className="rounded-full border border-line bg-panel px-2 py-0.5">{i + 1}. {s}</li>)}
      </ol>
      {!levers ? <Spinner /> : (
        <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
          <div className="space-y-4">
            <Card title="1. Policy problem">
              <div className="space-y-2">
                {levers.map((l: any) => (
                  <label key={l.id} className={`block cursor-pointer rounded-md border p-2 text-sm ${leverId === l.id ? "border-accent bg-accent-soft" : "border-line"}`}>
                    <input type="radio" className="mr-2" checked={leverId === l.id} onChange={() => setLeverId(l.id)} />
                    <b>{l.name}</b>
                    <div className="mt-1 text-xs text-muted">{l.question}</div>
                  </label>
                ))}
              </div>
            </Card>
            {lever && (
              <Card title="2–4. Baseline, intervention, parameters">
                <div className="space-y-3">
                  {Object.entries(params).map(([name, value]) => (
                    <ParameterInput key={name} name={name} value={value} help={lever.param_help[name]}
                      onChange={(v) => setParams({ ...params, [name]: v })} />
                  ))}
                  <Button onClick={runScenario} disabled={busy} className="w-full">{busy ? "Running 2,000 draws…" : "5. Run scenario"}</Button>
                  <ErrorAlert error={error} />
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            {!run ? (
              <Card><p className="text-sm text-muted">Set parameters and run a scenario. Try the zoning lever for a state such as Maharashtra.</p></Card>
            ) : (
              <>
                <Card title={run.lever_name} right={<span className="flex items-center gap-2"><DataLabel label="SIMULATED" /><Badge>run #{run.run_id}</Badge></span>}>
                  <p className="mb-2 text-lg" style={{ fontFamily: "var(--font-serif)" }}>{run.headline}</p>
                  {impact?.p50 !== undefined && (
                    <p className="text-sm text-muted">
                      Median {formatNumber(finalValue(impact.p50), 1)} · range P10 {formatNumber(finalValue(impact.p10), 1)} to P90{" "}
                      {formatNumber(finalValue(impact.p90), 1)} ({toTitleCase(impactKey)})
                    </p>
                  )}
                  <ScenarioFanChart run={run} />
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" onClick={keepForComparison}>Keep for comparison</Button>
                    <Button variant="ghost" onClick={reproduceRun}>Reproduce run</Button>
                    <Button onClick={async () => setBrief(await api.get(`/api/v1/simulations/runs/${run.run_id}/brief`))}>8. Export policy brief</Button>
                  </div>
                  <p className="mt-2 text-xs text-muted">{run.disclaimer} Seed {run.seed}; hash {run.hash.slice(0, 16)}…</p>
                </Card>
                <div className="grid gap-4 lg:grid-cols-2">
                  <Card title="6. What drives the result (tornado)"><SensitivityTornado run={run} /></Card>
                  <Card title="Context">
                    <dl className="text-sm">
                      {Object.entries(run.context).map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-2 border-b border-line/60 py-1">
                          <dt className="text-muted">{toTitleCase(k)}</dt>
                          <dd className="text-right">{Array.isArray(v) ? v.join(", ") : formatNumber(v, 3)}</dd>
                        </div>
                      ))}
                    </dl>
                  </Card>
                </div>
                <AssumptionsTable coefficients={run.coefficients} overrides={overrides} onOverride={setOverrides} />
              </>
            )}
            {savedScenarios.length > 0 && (
              <Card title="7. Compare scenarios">
                <DataTable rows={savedScenarios} columns={[
                  { key: "label", label: "Scenario" },
                  { key: "params", label: "Settings", render: (s) => (
                    <span className="text-xs">
                      {Object.entries(s.run.params).filter(([k, v]) => v !== null && k !== "coef_overrides").map(([k, v]) => `${k}=${v}`).join(", ")}
                    </span>
                  ) },
                  { key: "headline", label: "Result", render: (s) => s.run.headline },
                ]} />
              </Card>
            )}
            {brief && <PolicyBriefCard key={brief.sha256} brief={brief} runId={run.run_id} />}
          </div>
        </div>
      )}
    </PageContainer>
  );
}
