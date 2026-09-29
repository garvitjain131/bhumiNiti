import EChart from "@/components/charts/EChart";

/** Tornado chart: the result with each parameter at the low and high end of its range. */
export function SensitivityTornado({ run }: { run: any }) {
  const rows = [...run.tornado].reverse();
  return (
    <EChart height={Math.max(160, 40 * rows.length + 60)} option={{
      tooltip: { trigger: "axis" },
      grid: { left: 220, right: 24, top: 24, bottom: 24 },
      legend: { top: 0 },
      yAxis: { type: "category", data: rows.map((x: any) => x.parameter) },
      xAxis: { type: "value", name: run.unit },
      series: [
        { type: "bar", name: "Parameter at low end", data: rows.map((x: any) => x.low) },
        { type: "bar", name: "Parameter at high end", data: rows.map((x: any) => x.high) },
      ],
    }} />
  );
}
