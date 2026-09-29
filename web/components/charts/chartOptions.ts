import type { EChartsOption, SeriesOption } from "echarts";

/** Series colours: navy first, then saffron, green, teal, plum, ochre, violet and slate. */
export const CHART_PALETTE = ["#1a4d8f", "#e07b1a", "#1f7a45", "#1b7f86", "#8e2c48", "#b8860b", "#5b4b9a", "#6b7a90"];

function axisTheme(text: string, axis: string, split: string) {
  const axisStyle = { axisLine: { lineStyle: { color: axis } }, axisTick: { lineStyle: { color: axis } },
    axisLabel: { color: text }, splitLine: { lineStyle: { color: split } }, nameTextStyle: { color: text } };
  return { categoryAxis: axisStyle, valueAxis: axisStyle, logAxis: axisStyle, timeAxis: axisStyle };
}

/** ECharts themes matching the app's light and dark tokens. */
export const CHART_THEMES = {
  "lpip-light": {
    backgroundColor: "transparent", textStyle: { color: "#5a6677" }, legend: { textStyle: { color: "#5a6677" } },
    tooltip: { backgroundColor: "#ffffff", borderColor: "#dce2ea", textStyle: { color: "#17212f" } },
    ...axisTheme("#5a6677", "#c5cfdb", "#e8edf3"),
  },
  "lpip-dark": {
    backgroundColor: "transparent", textStyle: { color: "#98a4b6" }, legend: { textStyle: { color: "#98a4b6" } },
    tooltip: { backgroundColor: "#151e2d", borderColor: "#273347", textStyle: { color: "#e6ebf2" } },
    ...axisTheme("#98a4b6", "#34435a", "#1f2a3b"),
  },
};

export type LineSeries = { name: string; data: [number, number | null][]; dashed?: boolean };
export type UncertaintyBand = { name: string; lo: [number, number][]; hi: [number, number][] };

/** Line chart for [year, value] series, with an optional P10–P90 band. */
export function lineChartOption(series: LineSeries[], opts: { yName?: string; band?: UncertaintyBand } = {}): EChartsOption {
  const s: SeriesOption[] = series.map((x) => ({
    type: "line", name: x.name, data: x.data, showSymbol: x.data.length < 30, smooth: false,
    lineStyle: x.dashed ? { type: "dashed" } : undefined,
  }));
  if (opts.band) {
    const band = opts.band;
    s.push({ type: "line", name: band.name + " P10", data: band.lo, stack: "band", lineStyle: { opacity: 0 },
      showSymbol: false, silent: true } as SeriesOption);
    s.push({ type: "line", name: band.name + " P10–P90", stack: "band", showSymbol: false,
      data: band.hi.map(([x, y], i) => [x, y - band.lo[i][1]]), lineStyle: { opacity: 0 },
      areaStyle: { opacity: 0.18 }, silent: true } as SeriesOption);
  }
  return {
    legend: { top: 0, type: "scroll" },
    xAxis: { type: "value", min: "dataMin", max: "dataMax", axisLabel: { formatter: (v: number) => String(v) } },
    yAxis: { type: "value", name: opts.yName, nameTextStyle: { align: "left" }, scale: true },
    series: s,
  };
}

/** Bar chart for labelled values; horizontal for long category names. */
export function barChartOption(labels: string[], values: (number | null)[], opts: { horizontal?: boolean; name?: string } = {}): EChartsOption {
  const category = { type: "category" as const, data: labels, axisLabel: { interval: 0, width: 150, overflow: "truncate" as const } };
  const value = { type: "value" as const, name: opts.name };
  return {
    tooltip: { trigger: "axis" },
    grid: { left: opts.horizontal ? 160 : 48, right: 16, top: 24, bottom: opts.horizontal ? 24 : 60, containLabel: false },
    xAxis: opts.horizontal ? value : { ...category, axisLabel: { rotate: 30, interval: 0 } },
    yAxis: opts.horizontal ? { ...category, inverse: true } : value,
    series: [{ type: "bar", data: values, name: opts.name }],
  };
}
