import Link from "next/link";
import { useState } from "react";
import { Badge, Card, DataTable } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { WorkspaceCardProps } from "./types";

const STANCE_TONE: Record<string, "ok" | "danger" | "neutral"> = { supports: "ok", contradicts: "danger" };

export function EvidenceCollection({ workspace, workspaceId, canEdit, run }: WorkspaceCardProps) {
  const [bibliography, setBibliography] = useState("");
  const exportAs = async (format: "bibtex" | "ris") =>
    setBibliography((await api.get(`/api/v1/workspaces/${workspaceId}/bibliography`, { fmt: format })).text);

  return (
    <Card title={`Evidence collection (${workspace.items.length})`} right={
      <span className="flex gap-2 text-sm">
        <Link href="/search">Find evidence →</Link>
        <button className="text-accent underline" onClick={() => exportAs("bibtex")}>BibTeX</button>
        <button className="text-accent underline" onClick={() => exportAs("ris")}>RIS</button>
      </span>
    }>
      <DataTable rows={workspace.items} empty="Add evidence from Search or the Assistant." columns={[
        { key: "title", label: "Item", render: (i) => (
          <Link href={`/evidence/${encodeURIComponent(i.evidence_id)}`}>{i.evidence?.title ?? i.evidence_id}</Link>
        ) },
        { key: "stance", label: "Stance", render: (i) => i.stance && <Badge tone={STANCE_TONE[i.stance] ?? "neutral"}>{i.stance}</Badge> },
        { key: "actions", label: "", render: (i) => canEdit && (
          <button className="text-xs text-danger" onClick={() => run(() => api.del(`/api/v1/workspaces/${workspaceId}/items/${i.id}`))}>remove</button>
        ) },
      ]} />
      {bibliography && (
        <textarea readOnly className="mt-2 h-40 w-full rounded border border-line p-2 font-mono text-xs" value={bibliography} aria-label="Bibliography" />
      )}
    </Card>
  );
}
