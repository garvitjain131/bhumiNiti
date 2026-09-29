import { DataLabel } from "./DataLabel";

/** A figure with its label: ruled top edge, monospace value, definition on hover. */
export function KpiCard({ label, value, unit, note, dataLabel }: {
  label: string; value: React.ReactNode; unit?: string; note?: string; dataLabel?: string;
}) {
  return (
    <div className="rounded-[4px] border border-line border-t-2 border-t-accent bg-panel px-4 py-3" title={note}>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 font-mono text-[22px] font-semibold tabular-nums leading-tight">
        {value} {unit && <span className="font-sans text-xs font-normal text-muted">{unit}</span>}
      </div>
      {(note || dataLabel) && (
        <div className="mt-1.5 flex items-center gap-2 text-xs text-muted">
          {dataLabel && <DataLabel label={dataLabel} />}
          <span className="line-clamp-2">{note}</span>
        </div>
      )}
    </div>
  );
}
