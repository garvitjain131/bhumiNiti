import { FormField, inputClass } from "@/components/ui";
import { toTitleCase } from "@/lib/format";

/** Parameters expressed as a share (0–1) get a percentage slider. */
const FRACTION_PARAMS = ["strength", "compliance", "rccms_coverage", "ulpin_coverage"];

/** One simulation parameter: checkbox, percentage slider, or text/number field depending on its type. */
export function ParameterInput({ name, value, help, onChange }: {
  name: string; value: any; help?: string; onChange: (value: any) => void;
}) {
  if (name === "districts") return null;
  if (typeof value === "boolean" || name === "sia") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} /> {toTitleCase(name)}
        <span className="text-xs text-muted">{help}</span>
      </label>
    );
  }
  if (FRACTION_PARAMS.includes(name)) {
    return (
      <FormField label={`${toTitleCase(name)}: ${Math.round((value ?? 0) * 100)}%`} hint={help}>
        <input type="range" min={0} max={1} step={0.05} value={value ?? 0} onChange={(e) => onChange(Number(e.target.value))} className="w-full" />
      </FormField>
    );
  }
  return (
    <FormField label={toTitleCase(name)} hint={help}>
      <input className={inputClass} value={value ?? ""} type={typeof value === "number" ? "number" : "text"}
        onChange={(e) => onChange(typeof value === "number" ? Number(e.target.value) : e.target.value || null)} />
    </FormField>
  );
}
