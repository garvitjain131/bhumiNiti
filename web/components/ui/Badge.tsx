export type BadgeTone = "neutral" | "accent" | "warn" | "ok" | "danger";

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: "bg-subtle text-ink/80",
  accent: "bg-accent-soft text-accent",
  warn: "bg-amber-50 text-amber-800",
  ok: "bg-emerald-50 text-emerald-800",
  danger: "bg-red-50 text-red-800",
};

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: BadgeTone }) {
  return <span className={`inline-block rounded-[3px] px-1.5 py-0.5 text-[11px] font-medium ${TONE_CLASS[tone]}`}>{children}</span>;
}
