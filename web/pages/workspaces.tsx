import Link from "next/link";
import { useState } from "react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge, Button, Card, ErrorAlert, FormField, Spinner, inputClass } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";

const EMPTY_WORKSPACE = { name: "", question: "", geography: "", period: "" };

function NewWorkspaceForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState(EMPTY_WORKSPACE);
  const [error, setError] = useState<unknown>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/v1/workspaces", form);
      setForm(EMPTY_WORKSPACE);
      onCreated();
    } catch (x) {
      setError(x);
    }
  }

  return (
    <Card title="New workspace">
      <form onSubmit={create} className="space-y-3">
        <FormField label="Name">
          <input className={inputClass} required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <FormField label="Policy question">
          <textarea className={inputClass} required minLength={10} rows={3} value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} />
        </FormField>
        <FormField label="Geography">
          <input className={inputClass} value={form.geography} onChange={(e) => setForm({ ...form, geography: e.target.value })} />
        </FormField>
        <FormField label="Period">
          <input className={inputClass} value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} placeholder="e.g. 2010-2025" />
        </FormField>
        <ErrorAlert error={error} />
        <Button className="w-full">Create</Button>
      </form>
    </Card>
  );
}

export default function WorkspacesPage() {
  const { user } = useAuth();
  const signedIn = user.role !== "public";
  const { data: workspaces, error, reload } = useApi(signedIn ? "/api/v1/workspaces" : null, undefined, [user.role]);

  if (!signedIn) return <PageContainer title="Workspaces"><ErrorAlert error={{ status: 401, message: "" }} /></PageContainer>;
  return (
    <PageContainer title="Collaborative workspaces"
      subtitle="A workspace starts from a policy question. Researchers and officials collect evidence, write versioned notes, comment, assign tasks and send findings for review.">
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-3">
          <ErrorAlert error={error} />
          {!workspaces ? <Spinner /> : workspaces.length === 0 ? <p className="text-sm text-muted">No workspaces yet.</p> : workspaces.map((w: any) => (
            <Card key={w.id}>
              <Link href={`/workspaces/${w.id}`} className="text-lg" style={{ fontFamily: "var(--font-serif)" }}>{w.name}</Link>
              <p className="mt-1 text-sm">{w.question}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
                <Badge tone="accent">your role: {w.my_role}</Badge>
                <span>{w.items} evidence items</span>
                <span>· {w.members} members</span>
                <span>· owner {w.owner_name}</span>
                {w.geography && <span>· {w.geography}</span>}
              </div>
            </Card>
          ))}
        </div>
        <NewWorkspaceForm onCreated={reload} />
      </div>
    </PageContainer>
  );
}
