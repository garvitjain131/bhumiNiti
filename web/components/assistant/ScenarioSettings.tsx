import { useEffect, useState } from "react";
import { ParameterInput } from "@/components/policy-lab/ParameterInput";
import { Button, Card, FormField, inputClass } from "@/components/ui";
import { useApi } from "@/hooks/useApi";

export type ScenarioChoice = { lever: string | null; params: Record<string, any> | null; routes: string[] | null };

/** Optional controls: choose the policy to test and set its parameters. */
export function ScenarioSettings({ initial, onApply }: { initial: ScenarioChoice; onApply: (c: ScenarioChoice) => void }) {
  const { data: levers } = useApi("/api/v1/simulations/levers");
  const [lever, setLever] = useState<string>(initial.lever ?? "");
  const [params, setParams] = useState<Record<string, any>>(initial.params ?? {});
  const spec = levers?.find((l: any) => l.id === lever);

  useEffect(() => {
    setLever(initial.lever ?? "");
    setParams(initial.params ?? {});
  }, [initial.lever, initial.params]);

  function chooseLever(id: string) {
    setLever(id);
    setParams(levers?.find((l: any) => l.id === id)?.default_params ?? {});
  }

  return (
    <Card title="Scenario settings (optional)">
      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <FormField label="Policy to test">
          <select className={inputClass} value={lever} onChange={(e) => chooseLever(e.target.value)}>
            <option value="">Work it out from my question</option>
            {(levers ?? []).map((l: any) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          {spec && Object.entries(params).filter(([k]) => k !== "coef_overrides").map(([k, v]) => (
            <ParameterInput key={k} name={k} value={v} help={spec.param_help[k]} onChange={(nv) => setParams({ ...params, [k]: nv })} />
          ))}
          {!spec && <p className="text-sm text-muted">Choose a policy to set its details; otherwise they are read from your question.</p>}
        </div>
      </div>
      <Button className="mt-3" onClick={() => onApply({ lever: lever || null, params: lever ? params : null, routes: null })}>
        Ask again with these settings
      </Button>
    </Card>
  );
}
