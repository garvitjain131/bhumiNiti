/** Number formatting in Indian style (lakh, crore), "–" for missing values. */
export function formatNumber(v: unknown, digits = 1): string {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "number") {
    if (!isFinite(v)) return "–";
    const a = Math.abs(v);
    if (a >= 1e7) return (v / 1e7).toFixed(2) + " cr";
    if (a >= 1e5) return (v / 1e5).toFixed(2) + " lakh";
    return v.toLocaleString("en-IN", { maximumFractionDigits: digits });
  }
  return String(v);
}

/** "UTTAR_PRADESH" / "land_disputes" -> "Uttar Pradesh" / "Land Disputes". */
export function toTitleCase(s?: string | null): string {
  return (s ?? "")
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
