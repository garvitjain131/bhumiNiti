import Link from "next/link";
import { Card } from "@/components/ui";

const KIND_LABEL: Record<string, string> = { document: "Research", dataset: "Data", model: "Scenario model" };

/** Every source behind the answer: studies and documents, datasets, and the scenario model. */
export function SourcesPanel({ sources }: { sources: any[] }) {
  return (
    <Card title="Sources">
      {sources.length === 0 ? <p className="text-sm text-muted">No sources were used.</p> : (
        <ul className="space-y-2 text-sm">
          {sources.map((s: any) => (
            <li key={`${s.kind}-${s.ref}`} className="flex gap-2">
              <span className="mt-0.5 h-fit shrink-0 rounded-[3px] bg-subtle px-1.5 text-[11px]">{KIND_LABEL[s.kind] ?? s.kind}</span>
              <span>
                {s.kind === "document"
                  ? <Link href={`/evidence/${encodeURIComponent(s.ref)}`}>{s.title}</Link>
                  : s.kind === "model" ? <Link href="/policy-lab">{s.title}</Link> : s.title}
                <span className="text-xs text-muted">
                  {" · "}{s.detail ?? [s.year ?? "n.d.", s.type_group].filter(Boolean).join(" · ")}
                  {s.kind === "document" && !s.used ? " · related, not quoted in the answer" : ""}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
