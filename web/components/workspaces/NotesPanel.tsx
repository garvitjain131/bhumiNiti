import { useState } from "react";
import { Badge, Button, Card, inputClass } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import type { WorkspaceCardProps } from "./types";

const STATUS_TONE: Record<string, "ok" | "warn" | "danger" | "neutral"> = { approved: "ok", in_review: "warn", changes_requested: "danger" };
const EMPTY_NOTE = { title: "", body: "", note_key: undefined as string | undefined };

/** Versioned notes: editing saves a new version; notes go through draft → in review → approved. */
export function NotesPanel({ workspace, workspaceId, canEdit, run }: WorkspaceCardProps) {
  const { user } = useAuth();
  const [draft, setDraft] = useState(EMPTY_NOTE);
  const [history, setHistory] = useState<any[] | null>(null);
  const notesUrl = `/api/v1/workspaces/${workspaceId}/notes`;
  const canReview = workspace.my_role === "owner" || ["reviewer", "official", "admin"].includes(user.role);
  const setStatus = (noteId: number, status: string) => run(() => api.post(`${notesUrl}/${noteId}/status`, { status }));

  function save(e: React.FormEvent) {
    e.preventDefault();
    run(async () => {
      await api.post(notesUrl, { ...draft, note_key: draft.note_key || undefined });
      setDraft(EMPTY_NOTE);
    });
  }

  return (
    <Card title="Notes and findings (versioned, with review)">
      {workspace.notes.map((n: any) => (
        <div key={n.id} className="mb-3 border-b border-line pb-3 last:border-0">
          <div className="flex flex-wrap items-center gap-2">
            <b>{n.title}</b>
            <Badge>v{n.version}</Badge>
            <Badge tone={STATUS_TONE[n.status] ?? "neutral"}>{n.status.replace("_", " ")}</Badge>
            <span className="text-xs text-muted">{n.author} · {n.created_at}</span>
          </div>
          <p className="mt-1 whitespace-pre-line text-sm">{n.body}</p>
          <div className="mt-1 flex flex-wrap gap-2 text-xs">
            {canEdit && (
              <button className="text-accent underline" onClick={() => setDraft({ title: n.title, body: n.body, note_key: n.note_key })}>edit (new version)</button>
            )}
            {canEdit && n.status === "draft" && (
              <button className="text-accent underline" onClick={() => setStatus(n.id, "in_review")}>request review</button>
            )}
            {n.status === "in_review" && canReview && (
              <>
                <button className="text-ok underline" onClick={() => setStatus(n.id, "approved")}>approve</button>
                <button className="text-danger underline" onClick={() => setStatus(n.id, "changes_requested")}>request changes</button>
              </>
            )}
            <button className="text-muted underline" onClick={async () => setHistory(await api.get(`${notesUrl}/${n.note_key}/history`))}>history</button>
          </div>
        </div>
      ))}
      {history && (
        <div className="mb-3 rounded-md bg-subtle p-2 text-xs">
          <b>Version history</b> <button className="underline" onClick={() => setHistory(null)}>close</button>
          {history.map((h) => <div key={h.id} className="mt-1">v{h.version} · {h.author} · {h.created_at}: {h.body.slice(0, 120)}</div>)}
        </div>
      )}
      {canEdit && (
        <form className="space-y-2" onSubmit={save}>
          <input className={inputClass} placeholder="Note title" required value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          <textarea className={inputClass} rows={4} placeholder="Finding, analysis or draft" required value={draft.body}
            onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
          <Button>{draft.note_key ? "Save new version" : "Add note"}</Button>
        </form>
      )}
    </Card>
  );
}
