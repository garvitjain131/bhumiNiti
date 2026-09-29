import { Card, Spinner, inputClass } from "@/components/ui";

export type SelectedLayer = { kind: "metric" | "indicator"; id: string };

/** District metrics grouped by theme, plus time-series indicators with a year slider. */
export function LayerPicker({ layers, selected, onSelect, year, onYearChange }: {
  layers: any; selected: SelectedLayer; onSelect: (l: SelectedLayer) => void; year: number | ""; onYearChange: (y: number | "") => void;
}) {
  if (!layers) return <Card title="Layer"><Spinner /></Card>;

  const metricsByTheme: Record<string, any[]> = {};
  layers.district_metrics.forEach((m: any) => (metricsByTheme[m.theme] ??= []).push(m));
  const indicator = selected.kind === "indicator" ? layers.time_series_indicators.find((i: any) => i.indicator === selected.id) : null;
  const years = indicator ? Array.from({ length: indicator.year_to - indicator.year_from + 1 }, (_, i) => indicator.year_from + i) : [];

  return (
    <Card title="Layer">
      <div className="space-y-3 text-sm">
        {Object.entries(metricsByTheme).map(([theme, metrics]) => (
          <div key={theme}>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{theme}</div>
            {metrics.map((m) => (
              <label key={m.metric} className="flex cursor-pointer items-center gap-2 py-0.5">
                <input type="radio" name="layer" checked={selected.kind === "metric" && selected.id === m.metric}
                  onChange={() => onSelect({ kind: "metric", id: m.metric })} />
                <span>{m.name}</span>
              </label>
            ))}
          </div>
        ))}
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Time series (pick a year)</div>
          <select className={inputClass} value={selected.kind === "indicator" ? selected.id : ""}
            onChange={(e) => { onSelect({ kind: "indicator", id: e.target.value }); onYearChange(""); }}>
            <option value="">Choose an indicator…</option>
            {layers.time_series_indicators.filter((i: any) => i.year_to - i.year_from >= 3).map((i: any) => (
              <option key={i.indicator} value={i.indicator}>{i.name} ({i.year_from}–{i.year_to})</option>
            ))}
          </select>
          {years.length > 0 && (
            <div className="mt-2">
              <input type="range" min={years[0]} max={years[years.length - 1]} value={year || years[years.length - 1]}
                onChange={(e) => onYearChange(Number(e.target.value))} className="w-full" aria-label="Year" />
              <div className="text-center text-xs text-muted">Year: {year || "latest"}</div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
