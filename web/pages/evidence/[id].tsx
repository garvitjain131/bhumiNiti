import { useRouter } from "next/router";
import { useState } from "react";
import { EvidenceListItem } from "@/components/evidence/EvidenceListItem";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge, Button, Card, ErrorAlert, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { toTitleCase } from "@/lib/format";

function AddToWorkspace({ evidenceId }: { evidenceId: string }) {
  const { hasRole } = useAuth();
  const { data: workspaces } = useApi(hasRole("researcher") ? "/api/v1/workspaces" : null);
  const [message, setMessage] = useState("");
  if (!workspaces?.length) return null;

  async function add(workspaceId: number, stance: string) {
    await api.post(`/api/v1/workspaces/${workspaceId}/items`, { evidence_id: evidenceId, stance });
    setMessage("Added to workspace.");
  }

  return (
    <Card title="Add to a workspace">
      {workspaces.filter((w: any) => w.my_role !== "viewer").map((w: any) => (
        <div key={w.id} className="mb-2 text-sm">
          <div className="font-medium">{w.name}</div>
          <div className="mt-1 flex gap-1">
            {["supports", "contradicts", "context"].map((stance) => (
              <Button key={stance} variant="ghost" className="text-xs" onClick={() => add(w.id, stance)}>{stance}</Button>
            ))}
          </div>
        </div>
      ))}
      {message && <p className="text-sm text-ok">{message}</p>}
    </Card>
  );
}

export default function EvidenceDetailPage() {
  const router = useRouter();
  const evidenceId = typeof router.query.id === "string" ? router.query.id : null;
  const path = evidenceId ? `/api/v1/evidence/${encodeURIComponent(evidenceId)}` : null;
  const { data: item, error } = useApi(path);
  const { data: related } = useApi(path && `${path}/recommendations`);

  async function openPdf() {
    const res = await api.raw(`${path}/file`);
    window.open(URL.createObjectURL(await res.blob()), "_blank", "noopener");
  }

  if (error) return <PageContainer title="Evidence"><ErrorAlert error={error} /></PageContainer>;
  if (!item || !evidenceId) return <PageContainer title="Evidence"><Spinner /></PageContainer>;
  return (
    <PageContainer title={item.title} subtitle={
      <span className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">{item.type_group}</Badge>
        {item.year && <span>{item.year}</span>}
        {item.source_org && <span>· {item.source_org}</span>}
        <span>· source: {toTitleCase(item.source)}</span>
      </span>
    }>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Card title="Abstract / summary">
            <p className="whitespace-pre-line text-sm leading-relaxed">{item.abstract || "No abstract available."}</p>
          </Card>
          <Card title="Provenance">
            <dl className="grid grid-cols-[140px_1fr] gap-y-1 text-sm">
              <dt className="text-muted">Evidence ID</dt><dd className="font-mono text-xs">{item.evidence_id}</dd>
              {item.authors?.length > 0 && (<><dt className="text-muted">Authors</dt><dd>{item.authors.slice(0, 8).join(", ")}</dd></>)}
              {item.doi && (<><dt className="text-muted">DOI</dt><dd><a href={item.doi} target="_blank" rel="noopener noreferrer">{item.doi}</a></dd></>)}
              {item.url && (<><dt className="text-muted">Source page</dt><dd className="truncate"><a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a></dd></>)}
              <dt className="text-muted">Licence</dt><dd>{item.license ?? "see source"}</dd>
              <dt className="text-muted">States</dt><dd>{(item.states ?? []).join(", ") || "India / unspecified"}</dd>
              <dt className="text-muted">Themes</dt><dd>{(item.themes ?? []).map(toTitleCase).join(", ")}</dd>
              <dt className="text-muted">Method (auto)</dt><dd>{item.classification?.method}</dd>
              <dt className="text-muted">Finding (auto)</dt><dd>{item.classification?.direction} <span className="text-xs text-muted">(heuristic tag)</span></dd>
            </dl>
            {item.has_file && <Button className="mt-3" onClick={openPdf}>Open stored PDF</Button>}
          </Card>
        </div>
        <div className="space-y-4">
          <AddToWorkspace evidenceId={evidenceId} />
          <Card title="Related evidence">
            {!related ? <Spinner /> : related.map((r: any) => <EvidenceListItem key={r.evidence_id} item={r} />)}
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
