import EChart from "@/components/charts/EChart";
import { lineChartOption } from "@/components/charts/chartOptions";

/** Baseline vs policy median over time, with the policy's P10–P90 band. */
export function ScenarioFanChart({ run }: { run: any }) {
  const key = Object.keys(run.baseline)[0];
  const baseline = run.baseline[key];
  const scenario = run.scenario[key];
  const years: number[] = run.years;
  const toPoints = (values: number[]) => years.map((y, i) => [y, values[i]] as [number, number]);
  return (
    <EChart height={300} option={lineChartOption(
      [{ name: "Baseline (P50)", data: toPoints(baseline.p50) }, { name: "With policy (P50)", data: toPoints(scenario.p50) }],
      { yName: run.unit, band: { name: "With policy", lo: toPoints(scenario.p10), hi: toPoints(scenario.p90) } },
    )} />
  );
}
