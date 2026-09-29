import { useState } from "react";
import EChart from "@/components/charts/EChart";
import { lineChartOption } from "@/components/charts/chartOptions";
import { Card, DataLabel, ErrorAlert, FormField, inputClass } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { formatNumber, toTitleCase } from "@/lib/format";

export default function TrendsForecasts() {
  const { data: indicators } = useApi("/api/v1/indicators");
  const [settings, setSettings] = useState({ indicator: "modis_cropland", state: "", to_year: 2030 });
  const state = settings.state || undefined;
  const { data: trend, error } = useApi("/api/v1/analytics/trend", { indicator: settings.indicator, state });
  const { data: forecast } = useApi("/api/v1/analytics/forecast", { indicator: settings.indicator, state, to_year: settings.to_year });
  // Satellite land-cover indicators are stored as fractions; show them as percentages.
  const scale = settings.indicator.startsWith("dw_") || settings.indicator.startsWith("modis_") ? 100 : 1;

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <Card title="Settings">
        <div className="space-y-3">
          <FormField label="Indicator">
            <select className={inputClass} value={settings.indicator} onChange={(e) => setSettings({ ...settings, indicator: e.target.value })}>
              {(indicators ?? []).filter((i: any) => i.year_to - i.year_from >= 4).map((i: any) => (
                <option key={i.indicator} value={i.indicator}>{i.name}</option>
              ))}
            </select>
          </FormField>
          <FormField label="State (blank = India)">
            <input className={inputClass} value={settings.state} onChange={(e) => setSettings({ ...settings, state: e.target.value })} placeholder="e.g. Maharashtra" />
          </FormField>
          <FormField label="Forecast to">
            <input className={inputClass} type="number" min={2026} max={2040} value={settings.to_year}
              onChange={(e) => setSettings({ ...settings, to_year: Number(e.target.value) })} />
          </FormField>
        </div>
      </Card>
      <div className="space-y-4">
        <ErrorAlert error={error} />
        {trend && forecast && (
          <Card title={`${toTitleCase(settings.indicator)} · ${settings.state || "India"}`}
            right={<span className="flex gap-1"><DataLabel label="DESCRIPTIVE" /><DataLabel label="PREDICTED" /></span>}>
            <EChart height={320} option={lineChartOption(
              [
                { name: "Observed", data: trend.series.map((r: any) => [r.year, r.value * scale]) },
                { name: "Forecast P50", data: forecast.forecast.map((r: any) => [r.year, r.p50 * scale]), dashed: true },
              ],
              { band: {
                name: "80% interval",
                lo: forecast.forecast.map((r: any) => [r.year, r.p10 * scale]),
                hi: forecast.forecast.map((r: any) => [r.year, r.p90 * scale]),
              } },
            )} />
            <div className="grid gap-2 text-sm md:grid-cols-3">
              <div>
                Trend: <b>{formatNumber(trend.slope_per_year * scale, 3)}</b>/yr (95% CI {formatNumber(trend.slope_ci95[0] * scale, 3)} to {formatNumber(trend.slope_ci95[1] * scale, 3)})
              </div>
              <div>Kendall τ {formatNumber(trend.monotonic_trend.kendall_tau, 2)} (p = {formatNumber(trend.monotonic_trend.p_value, 3)})</div>
              {forecast.backtest ? (
                <div>Back-test MAPE {formatNumber(forecast.backtest.mape_pct, 1)}%; {forecast.backtest.inside_80pct_interval}/3 held-out years inside the 80% interval</div>
              ) : (
                <div className="text-muted">Back-test needs 7+ observed years</div>
              )}
            </div>
            <p className="mt-2 text-xs text-muted">Forecast model {forecast.model.id}: {forecast.model.method}. Assumption: {forecast.model.assumption}.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
