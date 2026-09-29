import { useEffect, useState } from "react";
import { DataLabel } from "@/components/ui";
import { api } from "@/lib/api/client";

/** Dynamic World classes, each with a colour and a texture (like a geological column: colour = class, pattern = texture). */
const CLASSES: { indicator: string; label: string; background: string }[] = [
  { indicator: "dw_crops", label: "Cropland", background: "radial-gradient(#8a6d1f 0.9px, transparent 1.2px) 0 0/7px 7px, #e3c15a" },
  { indicator: "dw_trees", label: "Trees", background: "repeating-linear-gradient(90deg, transparent 0 9px, rgb(0 0 0 / .18) 9px 10px), repeating-linear-gradient(0deg, transparent 0 6px, rgb(0 0 0 / .14) 6px 7px), #4f7a45" },
  { indicator: "dw_shrub_and_scrub", label: "Shrub & scrub", background: "repeating-linear-gradient(45deg, transparent 0 6px, rgb(0 0 0 / .16) 6px 7px), #93a86a" },
  { indicator: "dw_grass", label: "Grass", background: "repeating-linear-gradient(-45deg, transparent 0 7px, rgb(0 0 0 / .12) 7px 8px), #c2cf85" },
  { indicator: "dw_built", label: "Built-up", background: "repeating-linear-gradient(0deg, transparent 0 5px, rgb(255 255 255 / .35) 5px 6px), #a9553f" },
  { indicator: "dw_bare", label: "Bare", background: "radial-gradient(rgb(0 0 0 / .18) 0.8px, transparent 1px) 0 0/5px 5px, #dccaa8" },
  { indicator: "dw_water", label: "Water", background: "repeating-linear-gradient(0deg, transparent 0 4px, rgb(255 255 255 / .28) 4px 5px), #4d7fa8" },
  { indicator: "dw_flooded_vegetation", label: "Flooded vegetation", background: "#6c9a8b" },
  { indicator: "dw_snow_and_ice", label: "Snow & ice", background: "#e9eef1" },
];

type Band = { label: string; background: string; share: number };

/** India's land cover drawn to scale as one strip, from the platform's Dynamic World district panel. */
export function LandCoverStrip() {
  const [bands, setBands] = useState<Band[] | null>(null);
  const [year, setYear] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all(CLASSES.map((c) => api.get("/api/v1/analytics/trend", { indicator: c.indicator }).catch(() => null)))
      .then((results) => {
        if (!live) return;
        const latest = results.map((r) => r?.series?.at(-1));
        const total = latest.reduce((s, x) => s + (x?.value ?? 0), 0) || 1;
        setYear(latest.find(Boolean)?.year ?? null);
        setBands(CLASSES.map((c, i) => ({ label: c.label, background: c.background, share: ((latest[i]?.value ?? 0) / total) * 100 }))
          .filter((b) => b.share > 0.3));
      });
    return () => { live = false; };
  }, []);

  if (!bands) return <div className="h-[84px] animate-pulse rounded-[3px] bg-subtle" aria-hidden />;
  const starts = bands.map((_, i) => bands.slice(0, i).reduce((sum, b) => sum + b.share, 0));
  return (
    <figure>
      <div className="relative h-5 text-xs text-muted" aria-hidden>
        {bands.map((b, i) => b.share >= 7 && (
          <span key={b.label} className="absolute top-0 whitespace-nowrap" style={{ left: `calc(${starts[i]}% + 6px)` }}>{b.label}</span>
        ))}
      </div>
      <div className="flex h-10 overflow-hidden rounded-[3px] border border-line" role="img"
        aria-label={`Land cover of India${year ? `, ${year}` : ""}: ` + bands.map((b) => `${b.label} ${b.share.toFixed(1)}%`).join(", ")}>
        {bands.map((b) => (
          <div key={b.label} className="h-full border-r border-white/70 last:border-r-0 dark:border-black/40" style={{ width: `${b.share}%`, background: b.background }}
            title={`${b.label}: ${b.share.toFixed(1)}% of land area`} />
        ))}
      </div>
      <div className="relative mt-1 h-5 font-mono text-[11px] text-muted" aria-hidden>
        {[0, 20, 40, 60, 80, 100].map((t) => (
          <span key={t} className="absolute top-0 -translate-x-1/2 border-l border-line pl-1 pt-1 first:translate-x-0 last:-translate-x-full"
            style={{ left: `${t}%` }}>{t}%</span>
        ))}
      </div>
      <figcaption className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        <DataLabel label="ESTIMATED" />
        Land cover of India{year ? `, ${year}` : ""}: Dynamic World 10 m class shares of land area across all districts, drawn to scale.
        Colour = class, pattern = texture.
      </figcaption>
    </figure>
  );
}
