const LABEL_STYLE: Record<string, string> = {
  OBSERVED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  ESTIMATED: "bg-sky-50 text-sky-800 border-sky-200",
  SIMULATED: "bg-violet-50 text-violet-800 border-violet-200",
  PREDICTED: "bg-amber-50 text-amber-800 border-amber-200",
  CORRELATIONAL: "bg-orange-50 text-orange-800 border-orange-200",
  DESCRIPTIVE: "bg-slate-50 text-slate-700 border-slate-200",
  SYNTHETIC: "bg-rose-50 text-rose-800 border-rose-200",
};

/** Every number on screen says what kind of evidence it is. */
export function DataLabel({ label }: { label?: string | null }) {
  if (!label) return null;
  const key = Object.keys(LABEL_STYLE).find((k) => label.toUpperCase().startsWith(k)) ?? "DESCRIPTIVE";
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${LABEL_STYLE[key]}`}>
      {label.toUpperCase().split(" ")[0]}
    </span>
  );
}
