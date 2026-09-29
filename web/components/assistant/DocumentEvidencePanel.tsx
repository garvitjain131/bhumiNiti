import Link from "next/link";
import { Badge, Card, DataTable } from "@/components/ui";

const DIRECTION_TONE: Record<string, "ok" | "danger" | "neutral"> = { positive: "ok", negative: "danger" };

/** RAG output: retrieved sources with provenance and the study matrix (method and direction per source). */
export function DocumentEvidencePanel({ document }: { document: any }) {
  if (!document) return <p className="text-sm text-muted">This question did not need research documents.</p>;
  return (
    <div className="space-y-4">
      <Card title={`Research found (${document.sources.length})`}>
        <DataTable rows={document.sources} empty="Nothing retrieved." columns={[
          { key: "title", label: "Source", render: (r) => <Link href={`/evidence/${encodeURIComponent(r.evidence_id)}`}>{r.title}</Link> },
          { key: "year", label: "Year" },
          { key: "type_group", label: "Type" },
          { key: "source", label: "Provenance", render: (r) => <span className="text-xs">{r.source_org ?? r.source}</span> },
        ]} />
      </Card>
      {document.matrix.length > 0 && (
        <Card title="How each study was done and what it found">
          <DataTable rows={document.matrix} columns={[
            { key: "title", label: "Study", render: (r) => <Link href={`/evidence/${encodeURIComponent(r.evidence_id)}`}>{r.title?.slice(0, 90)}</Link> },
            { key: "year", label: "Year" },
            { key: "region", label: "Region" },
            { key: "method", label: "Method" },
            { key: "direction", label: "Finding", render: (r) => <Badge tone={DIRECTION_TONE[r.direction] ?? "neutral"}>{r.direction}</Badge> },
          ]} />
          <p className="mt-2 text-xs text-muted">Method and finding are tagged automatically from abstracts; open the source to check.</p>
        </Card>
      )}
    </div>
  );
}
