/** Colour and wording per evidence type, shared by every assistant panel. */
export const EVIDENCE_TYPES: Record<string, { label: string; chip: string; dot: string }> = {
  document: { label: "Research", chip: "border-teal-300 bg-teal-50 text-teal-900", dot: "bg-teal-600" },
  analytics: { label: "Data", chip: "border-sky-300 bg-sky-50 text-sky-900", dot: "bg-sky-600" },
  simulation: { label: "Scenario", chip: "border-violet-300 bg-violet-50 text-violet-900", dot: "bg-violet-600" },
  assumption: { label: "Model assumption", chip: "border-amber-300 bg-amber-50 text-amber-900", dot: "bg-amber-500" },
  conflict: { label: "Conflict between sources", chip: "border-orange-300 bg-orange-50 text-orange-900", dot: "bg-orange-500" },
  uncertainty: { label: "Uncertainty", chip: "border-stone-300 bg-stone-50 text-stone-800", dot: "bg-stone-500" },
  gap: { label: "Evidence gap", chip: "border-rose-300 bg-rose-50 text-rose-900", dot: "bg-rose-500" },
  overview: { label: "Summary", chip: "border-stone-300 bg-white text-ink", dot: "bg-stone-400" },
};

export const STATUS_TONE: Record<string, "ok" | "accent" | "warn" | "danger" | "neutral"> = {
  verified: "ok", simulated: "accent", assumption: "warn", conflict: "danger", correlational: "warn",
  pass: "ok", warn: "warn", fail: "danger",
};

export const SEVERITY_TONE: Record<string, "danger" | "warn" | "neutral"> = { high: "danger", medium: "warn", low: "neutral" };

export const claimAnchor = (id: string) => `claim-${id}`;
