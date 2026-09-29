import { formatNumber } from "@/lib/format";

/** Colour key for a stepped choropleth: one swatch per class, plus "no data". */
export function MapLegend({ breaks, colors }: { breaks: number[]; colors: string[] }) {
  const classLabel = (i: number) =>
    i === 0 ? `< ${formatNumber(breaks[0], 2)}`
      : i === colors.length - 1 ? `≥ ${formatNumber(breaks[i - 1], 2)}`
        : `${formatNumber(breaks[i - 1], 2)}–`;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
      {colors.map((c, i) => (
        <span key={i} className="flex items-center gap-1">
          <span className="inline-block h-3 w-5 rounded-sm" style={{ background: c }} />
          {classLabel(i)}
        </span>
      ))}
      <span className="ml-2 flex items-center gap-1"><span className="inline-block h-3 w-5 rounded-sm bg-[#d6d3cc]" /> no data</span>
    </div>
  );
}
