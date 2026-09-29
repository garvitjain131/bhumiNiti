import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { useTheme } from "@/lib/theme/ThemeProvider";
import { CHART_PALETTE, CHART_THEMES } from "./chartOptions";

let themesRegistered = false;
function registerThemes() {
  if (themesRegistered) return;
  for (const [name, theme] of Object.entries(CHART_THEMES)) echarts.registerTheme(name, theme);
  themesRegistered = true;
}

/** Minimal ECharts wrapper (React 19 compatible); follows the app's light/dark theme. */
export default function EChart({ option, height = 280, onClick }: {
  option: echarts.EChartsOption; height?: number; onClick?: (params: any) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const latestOption = useRef(option);
  const { theme } = useTheme();

  const apply = (o: echarts.EChartsOption) =>
    chart.current?.setOption({
      color: CHART_PALETTE,
      textStyle: { fontFamily: "Segoe UI, Noto Sans, sans-serif" },
      grid: { left: 48, right: 16, top: 32, bottom: 36, containLabel: true },
      tooltip: { trigger: "axis" },
      ...o,
    }, true);

  // (re)create the chart when the theme changes, then draw the latest option
  useEffect(() => {
    if (!container.current) return;
    registerThemes();
    chart.current = echarts.init(container.current, `lpip-${theme}`, { renderer: "canvas" });
    apply(latestOption.current);
    const observer = new ResizeObserver(() => chart.current?.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, [theme]);

  useEffect(() => {
    latestOption.current = option;
    apply(option);
  }, [option]);

  useEffect(() => {
    if (!chart.current || !onClick) return;
    chart.current.on("click", onClick);
    return () => {
      chart.current?.off("click", onClick);
    };
  }, [onClick, theme]);

  return <div ref={container} style={{ height, width: "100%" }} role="img" aria-label="chart" />;
}
