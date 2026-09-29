// Colour scales for choropleths. Kept free of MapLibre imports so server components can use them.

/** Quantile class breaks for a set of values (duplicates removed). */
export function quantiles(values: number[], n = 6): number[] {
  const v = values.filter((x) => x !== null && x !== undefined && isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return [];
  const out: number[] = [];
  for (let i = 1; i < n; i++) out.push(v[Math.floor((i / n) * (v.length - 1))]);
  return [...new Set(out)];
}
/** Sequential palette (low to high). */
export const SEQUENTIAL_COLORS = ["#f1f7f5", "#cde6e0", "#9ccfc4", "#5fb0a3", "#2b8c80", "#0f6e6e", "#08494b"];
/** Diverging palette (negative to positive). */
export const DIVERGING_COLORS = ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"];
