import { inputClass } from "@/components/ui";
import { STATE_FILTER_OPTIONS } from "@/config/geography";

/** State selector; the empty value means all of India. */
export function StateFilter({ value, onChange }: { value: string; onChange: (state: string) => void }) {
  return (
    <div className="mb-3 max-w-xs">
      <select className={inputClass} value={value} onChange={(e) => onChange(e.target.value)} aria-label="State">
        {STATE_FILTER_OPTIONS.map((s) => <option key={s} value={s}>{s || "All India"}</option>)}
      </select>
    </div>
  );
}
