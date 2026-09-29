import Link from "next/link";
import { Badge } from "@/components/ui";

export type EvidenceSummary = {
  evidence_id: string; title: string; type?: string; type_group?: string; year?: number | null; source_org?: string | null;
  states?: string[]; has_file?: boolean; snippet?: string | null; because?: string[];
};

/** One row in a list of evidence items (search results, recommendations, workspace items). */
export function EvidenceListItem({ item, action }: { item: EvidenceSummary; action?: React.ReactNode }) {
  return (
    <article className="border-b border-line py-3 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/evidence/${encodeURIComponent(item.evidence_id)}`} className="font-medium text-ink hover:text-accent">
            {item.title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <Badge tone="accent">{item.type_group ?? item.type}</Badge>
            {item.year && <span>{item.year}</span>}
            {item.source_org && <span>· {item.source_org}</span>}
            {(item.states ?? []).slice(0, 3).map((s) => <Badge key={s}>{s}</Badge>)}
            {item.has_file && <Badge tone="ok">PDF</Badge>}
          </div>
          {item.snippet && <p className="mt-1 line-clamp-2 text-sm text-muted">{item.snippet}</p>}
          {item.because && <p className="mt-1 text-xs text-accent">Recommended because: {item.because.join("; ")}</p>}
        </div>
        {action}
      </div>
    </article>
  );
}
