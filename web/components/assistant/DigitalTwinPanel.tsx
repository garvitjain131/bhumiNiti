import Link from "next/link";
import { ScenarioFanChart } from "@/components/policy-lab/ScenarioFanChart";
import { SensitivityTornado } from "@/components/policy-lab/SensitivityTornado";
import { Badge, Card, DataLabel, DataTable } from "@/components/ui";
import { formatNumber, toTitleCase } from "@/lib/format";

const LEVEL_TONE: Record<string, "danger" | "warn" | "neutral"> = { high: "danger", medium: "warn", low: "neutral" };
const GRADE_TONE: Record<string, "ok" | "accent" | "warn" | "neutral"> = { A: "ok", B: "accent", C: "warn", user: "neutral" };
const n = (v: any, d = 1) => (typeof v === "number" ? formatNumber(v, d) : v ?? "–");

function CurrentState({ state }: { state: any }) {
  return (
    <Card title={`Current state · ${state.scope}`} right={<Badge>baseline</Badge>}>
      <DataTable rows={state.indicators} columns={[
        { key: "name", label: "Indicator" },
        { key: "value", label: "Value", align: "right", render: (r) => `${n(r.value, 2)} ${r.unit}` },
        { key: "dataset", label: "Dataset", render: (r) => <span className="text-xs">{r.dataset} · {r.period}</span> },
        { key: "label", label: "", render: (r) => r.label === "ASSUMPTION" ? <Badge tone="warn">assumed input</Badge> : <DataLabel label={r.label} /> },
      ]} />
      <p className="mt-2 text-xs text-muted">{state.statement} {state.data_quality.join(" ")}</p>
    </Card>
  );
}

function PolicyLever({ twin }: { twin: any }) {
  const p = twin.policy_lever;
  const shown = Object.entries(p.parameters).filter(([k, v]) => k !== "coef_overrides" && v !== null && !(Array.isArray(v) && !v.length));
  return (
    <Card title={`Policy lever · ${twin.lever_name}`} right={<Badge tone="accent">intervention</Badge>}>
      <p className="mb-2 text-sm text-muted">{twin.lever_question}</p>
      <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-y-1 text-sm">
        {shown.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted" title={p.param_help[k]}>{toTitleCase(k)}</dt>
            <dd className="text-right tabular-nums">{Array.isArray(v) ? `${v.length} districts` : String(v)}</dd>
          </div>
        ))}
      </dl>
      {p.mapped_from_question.length > 0 && <p className="mt-2 text-xs text-muted">Read from the question: {p.mapped_from_question.join("; ")}.</p>}
      <p className="mt-2 text-xs text-muted">{p.statement}</p>
    </Card>
  );
}

/** Policy Digital Twin: current state + lever -> Monte Carlo scenario -> distribution, stress test, sensitivity. */
export function DigitalTwinPanel({ twin }: { twin: any }) {
  if (!twin) return <p className="text-sm text-muted">This question did not ask about a policy change, so no scenario was run.</p>;
  if (twin.status !== "ok") {
    return (
      <Card title="Policy scenario">
        <p className="text-sm">{twin.message}</p>
        {twin.available_levers && (
          <ul className="mt-2 list-disc pl-5 text-sm">{twin.available_levers.map((l: any) => <li key={l.id}><b>{l.name}</b>: {l.question}</li>)}</ul>
        )}
      </Card>
    );
  }
  const sim = twin.simulation;
  const stress = twin.stress_test;
  return (
    <div className="space-y-4">
      <p className="rounded-md border border-violet-200 bg-violet-50 p-3 text-sm">
        <DataLabel label="SIMULATED" /> Everything below the current state is a simulation under stated assumptions, not a prediction or an
        observed fact. Baseline and intervention are kept separate: <b>baseline state + policy lever + parameters → scenario</b>.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <CurrentState state={twin.current_state} />
        <PolicyLever twin={twin} />
      </div>

      <Card title="Baseline vs policy scenario" right={<span className="flex items-center gap-2"><DataLabel label="SIMULATED" />
        {twin.run.run_id && <Badge>run #{twin.run.run_id}</Badge>}</span>}>
        <DataTable rows={twin.comparison} columns={[
          { key: "indicator", label: "Indicator" },
          { key: "baseline_p50", label: "Baseline (P50)", align: "right", render: (r) => n(r.baseline_p50) },
          { key: "scenario_p50", label: "Scenario (P50)", align: "right", render: (r) => n(r.scenario_p50) },
          { key: "absolute_change", label: "Change", align: "right", render: (r) => n(r.absolute_change) },
          { key: "relative_change_pct", label: "Change %", align: "right", render: (r) => r.relative_change_pct === null ? "–" : `${n(r.relative_change_pct)}%` },
          { key: "range", label: "Scenario P10–P90", align: "right", render: (r) => `${n(r.scenario_p10)} – ${n(r.scenario_p90)}` },
          { key: "unit", label: "Unit" },
        ]} />
        <p className="mt-3 text-sm">
          Impact ({sim.impact_name}): P10 <b>{n(sim.impact.p10)}</b> · P50 <b>{n(sim.impact.p50)}</b> · P90 <b>{n(sim.impact.p90)}</b> {sim.impact_unit},
          from {sim.draws.toLocaleString("en-IN")} Monte Carlo draws (seed {sim.seed}).
        </p>
        <ScenarioFanChart run={twin.run} />
        <p className="text-xs text-muted">
          Model {twin.model_id} · hash {sim.hash.slice(0, 16)}… · <Link href={twin.run.run_id ? `/policy-lab?run=${twin.run.run_id}` : "/policy-lab"}>open this scenario in the Policy Lab</Link> to
          change coefficient ranges, compare scenarios and export a verifiable brief.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Stress test" right={<Badge tone={stress.stability === "relatively stable" ? "ok" : stress.stability === "highly sensitive" ? "danger" : "warn"}>{stress.stability}</Badge>}>
          <DataTable rows={stress.scenarios} columns={[
            { key: "scenario", label: "Assumptions" },
            { key: "p10", label: "P10", align: "right", render: (r) => n(r.p10) },
            { key: "p50", label: "P50", align: "right", render: (r) => n(r.p50) },
            { key: "p90", label: "P90", align: "right", render: (r) => n(r.p90) },
            { key: "unit", label: "Unit" },
          ]} />
          <p className="mt-2 text-xs text-muted">{stress.method}{stress.relative_spread !== null && ` Spread between conservative and high-impact medians: ${Math.round(stress.relative_spread * 100)}% of the central median.`}</p>
        </Card>
        <Card title="Sensitivity: what matters most">
          <SensitivityTornado run={twin.run} />
          <DataTable rows={twin.sensitivity} columns={[
            { key: "parameter", label: "Variable" },
            { key: "level", label: "Sensitivity", render: (r) => <Badge tone={LEVEL_TONE[r.level]}>{r.level}</Badge> },
            { key: "grade", label: "Evidence", render: (r) => <Badge tone={GRADE_TONE[r.grade] ?? "neutral"}>grade {r.grade}</Badge> },
          ]} />
        </Card>
      </div>

      <Card title="Evidence behind this scenario">
        <div className="grid gap-4 text-sm lg:grid-cols-2">
          <div>
            <div className="font-medium">Datasets that build the baseline</div>
            <ul className="mb-3 list-disc pl-5">{twin.evidence_behind.baseline_datasets.map((d: string) => <li key={d}>{d}</li>)}</ul>
            <div className="font-medium">What is simulated</div>
            <ul className="list-disc pl-5">{twin.evidence_behind.simulated_parts.map((d: string) => <li key={d}>{d}</li>)}</ul>
          </div>
          <div>
            <div className="font-medium">Relationships and their evidence</div>
            {twin.evidence_behind.relationships.map((r: any) => (
              <div key={r.parameter} className="mt-1 border-b border-line/60 pb-1">
                <div>{r.parameter} <Badge tone={GRADE_TONE[r.grade] ?? "neutral"}>grade {r.grade}</Badge></div>
                <div className="text-xs text-muted">{r.note}</div>
                {r.literature.map((l: any) => (
                  <Link key={l.evidence_id} href={`/evidence/${encodeURIComponent(l.evidence_id)}`} className="block truncate text-xs">{l.title} ({l.year ?? "n.d."})</Link>
                ))}
              </div>
            ))}
          </div>
        </div>
        <div className="mt-3">
          <DataTable rows={twin.evidence_behind.assumptions} columns={[
            { key: "name", label: "Assumption" },
            { key: "range", label: "Range", render: (r) => `${n(r.range[0], 3)} – ${n(r.range[1], 3)} ${r.unit}` },
            { key: "grade", label: "Grade", render: (r) => <Badge tone={GRADE_TONE[r.grade] ?? "neutral"}>{r.grade}</Badge> },
            { key: "source", label: "Source", render: (r) => <span className="text-xs">{r.source}</span> },
          ]} />
          <p className="mt-2 text-xs text-muted">Grades: A = Indian quasi-experimental study; B = estimated from platform data or international evidence; C = expert assumption.</p>
        </div>
      </Card>
    </div>
  );
}
