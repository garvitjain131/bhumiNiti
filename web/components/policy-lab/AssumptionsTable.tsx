import { Badge, Card, DataTable } from "@/components/ui";

export type CoefficientOverrides = Record<string, [number, number]>;

const GRADE_TONE: Record<string, "ok" | "accent" | "neutral" | "warn"> = { A: "ok", B: "accent", user: "neutral" };
const round3 = (v: number) => +Number(v).toPrecision(3);

/** Model coefficients with their evidence grade; each range can be overridden before the next run. */
export function AssumptionsTable({ coefficients, overrides, onOverride }: {
  coefficients: any[]; overrides: CoefficientOverrides; onOverride: (o: CoefficientOverrides) => void;
}) {
  const setBound = (c: any, bound: 0 | 1, value: number) => {
    const current: [number, number] = overrides[c.key] ?? [c.low, c.high];
    const next: [number, number] = bound === 0 ? [value, current[1]] : [current[0], value];
    onOverride({ ...overrides, [c.key]: next });
  };

  return (
    <Card title="6. Assumptions and evidence grades (override any range)">
      <DataTable rows={coefficients} columns={[
        { key: "name", label: "Coefficient" },
        { key: "range", label: "Range", render: (c) => (
          <span className="flex items-center gap-1">
            <input className="w-16 rounded border border-line px-1 text-xs" defaultValue={round3(c.low)}
              onBlur={(e) => setBound(c, 0, Number(e.target.value))} aria-label={`${c.name} low`} />
            –
            <input className="w-16 rounded border border-line px-1 text-xs" defaultValue={round3(c.high)}
              onBlur={(e) => setBound(c, 1, Number(e.target.value))} aria-label={`${c.name} high`} />
            <span className="text-xs text-muted">{c.unit}</span>
          </span>
        ) },
        { key: "grade", label: "Grade", render: (c) => <Badge tone={GRADE_TONE[c.grade] ?? "warn"}>{c.grade}</Badge> },
        { key: "source", label: "Source" },
      ]} />
      <p className="mt-2 text-xs text-muted">
        Grades: A = Indian quasi-experimental study; B = estimated from this platform&apos;s data or international evidence;
        C = expert assumption (widest range; a research gap). Edit a range, then run again.
      </p>
    </Card>
  );
}
