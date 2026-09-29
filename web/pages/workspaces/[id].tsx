import { useRouter } from "next/router";
import { useState } from "react";
import { EvidenceListItem } from "@/components/evidence/EvidenceListItem";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge, Button, Card, ErrorAlert, Spinner } from "@/components/ui";
import { EvidenceCollection } from "@/components/workspaces/EvidenceCollection";
import { NotesPanel } from "@/components/workspaces/NotesPanel";
import { DiscussionCard, MembersCard, TasksCard } from "@/components/workspaces/TeamCards";
import type { RunAction } from "@/components/workspaces/types";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function WorkspaceDetailPage() {
  const router = useRouter();
  const workspaceId = typeof router.query.id === "string" ? router.query.id : null;
  const { user } = useAuth();
  const { data: workspace, error, reload } = useApi(
    user.role !== "public" && workspaceId ? `/api/v1/workspaces/${workspaceId}` : null, undefined, [user.role],
  );
  const { data: recommendations } = useApi(
    workspace ? `/api/v1/workspaces/${workspaceId}/recommendations` : null, undefined, [workspace?.items?.length],
  );
  const [actionError, setActionError] = useState<unknown>(null);

  const run: RunAction = async (change) => {
    setActionError(null);
    try {
      await change();
      reload();
    } catch (e) {
      setActionError(e);
    }
  };

  if (error) return <PageContainer title="Workspace"><ErrorAlert error={error} /></PageContainer>;
  if (!workspace || !workspaceId) return <PageContainer title="Workspace"><Spinner /></PageContainer>;
  const canEdit = ["owner", "editor"].includes(workspace.my_role);
  const cardProps = { workspace, workspaceId, canEdit, run };

  return (
    <PageContainer title={workspace.name}
      subtitle={<><b>Question:</b> {workspace.question}{workspace.geography && <> · {workspace.geography}</>}{workspace.period && <> · {workspace.period}</>}</>}
      actions={<Badge tone="accent">your role: {workspace.my_role}</Badge>}>
      <ErrorAlert error={actionError} />
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <EvidenceCollection {...cardProps} />
          <NotesPanel {...cardProps} />
        </div>
        <div className="space-y-4">
          <MembersCard {...cardProps} />
          <TasksCard {...cardProps} />
          <DiscussionCard {...cardProps} />
          <Card title="Recommended for this collection">
            {!recommendations ? <Spinner /> : recommendations.slice(0, 6).map((r: any) => (
              <EvidenceListItem key={r.evidence_id} item={r} action={canEdit && (
                <Button variant="ghost" className="text-xs"
                  onClick={() => run(() => api.post(`/api/v1/workspaces/${workspaceId}/items`, { evidence_id: r.evidence_id }))}>+ add</Button>
              )} />
            ))}
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
