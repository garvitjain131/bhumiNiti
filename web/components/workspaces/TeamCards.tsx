import { useState } from "react";
import { Button, Card, inputClass } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { WorkspaceCardProps } from "./types";

export function MembersCard({ workspace, workspaceId, run }: WorkspaceCardProps) {
  const [member, setMember] = useState({ email: "", role: "editor" });
  return (
    <Card title="Members">
      {workspace.members.map((m: any) => (
        <div key={m.id} className="text-sm">{m.name} <span className="text-xs text-muted">· {m.role} · {m.institution ?? m.platform_role}</span></div>
      ))}
      {workspace.my_role === "owner" && (
        <form className="mt-2 flex gap-1" onSubmit={(e) => { e.preventDefault(); run(() => api.post(`/api/v1/workspaces/${workspaceId}/members`, member)); }}>
          <input className={inputClass} placeholder="email" value={member.email} onChange={(e) => setMember({ ...member, email: e.target.value })} />
          <select className="rounded border border-line text-sm" value={member.role} onChange={(e) => setMember({ ...member, role: e.target.value })}>
            <option>editor</option>
            <option>viewer</option>
          </select>
          <Button>Add</Button>
        </form>
      )}
    </Card>
  );
}

export function TasksCard({ workspace, workspaceId, canEdit, run }: WorkspaceCardProps) {
  const [task, setTask] = useState({ title: "", assignee_email: "" });
  return (
    <Card title="Tasks">
      {workspace.tasks.map((t: any) => (
        <label key={t.id} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={t.status === "done"} disabled={!canEdit}
            onChange={() => run(() => api.post(`/api/v1/workspaces/${workspaceId}/tasks/${t.id}/toggle`))} />
          <span className={t.status === "done" ? "line-through text-muted" : ""}>{t.title}</span>
          {t.assignee && <span className="text-xs text-muted">· {t.assignee}</span>}
        </label>
      ))}
      {canEdit && (
        <form className="mt-2 space-y-1" onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await api.post(`/api/v1/workspaces/${workspaceId}/tasks`, task);
            setTask({ title: "", assignee_email: "" });
          });
        }}>
          <input className={inputClass} placeholder="New task" required value={task.title} onChange={(e) => setTask({ ...task, title: e.target.value })} />
          <input className={inputClass} placeholder="Assign to (email, optional)" value={task.assignee_email}
            onChange={(e) => setTask({ ...task, assignee_email: e.target.value })} />
          <Button variant="ghost">Add task</Button>
        </form>
      )}
    </Card>
  );
}

export function DiscussionCard({ workspace, workspaceId, run }: WorkspaceCardProps) {
  const [comment, setComment] = useState("");
  return (
    <Card title="Discussion">
      {workspace.comments.map((c: any) => <p key={c.id} className="mb-1 text-sm"><b>{c.author}:</b> {c.body}</p>)}
      <form className="mt-2 flex gap-1" onSubmit={(e) => {
        e.preventDefault();
        run(async () => {
          await api.post(`/api/v1/workspaces/${workspaceId}/comments`, { body: comment });
          setComment("");
        });
      }}>
        <input className={inputClass} required value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment" />
        <Button>Post</Button>
      </form>
    </Card>
  );
}
