import { SignInLink } from "@/components/auth/SignInLink";
import { useState } from "react";
import { Badge, Button, Card, DataTable, ErrorAlert, FormField, inputClass } from "@/components/ui";
import { CONTRIBUTION_KINDS, FINDING_DIRECTIONS } from "@/config/innovation";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { toTitleCase } from "@/lib/format";

const EMPTY_FINDING = { kind: "finding", title: "", abstract: "", method: "", finding_direction: "", states: "", themes: "", url: "" };
const splitList = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

function SubmitFindingForm({ onSubmitted, onError }: { onSubmitted: () => void; onError: (e: unknown) => void }) {
  const [form, setForm] = useState(EMPTY_FINDING);
  const [confirmation, setConfirmation] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    onError(null);
    setConfirmation("");
    try {
      await api.post("/api/v1/contributions", {
        ...form, finding_direction: form.finding_direction || null, states: splitList(form.states), themes: splitList(form.themes),
      });
      setConfirmation("Submitted for review. Once approved it becomes searchable and counts in the Gap Radar.");
      onSubmitted();
    } catch (x) {
      onError(x);
    }
  }

  const set = (key: keyof typeof EMPTY_FINDING) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [key]: e.target.value });

  return (
    <form onSubmit={submit} className="space-y-2">
      <select className={inputClass} value={form.kind} onChange={set("kind")}>
        {CONTRIBUTION_KINDS.map((k) => <option key={k} value={k}>{toTitleCase(k)}</option>)}
      </select>
      <input className={inputClass} placeholder="Title" required minLength={5} value={form.title} onChange={set("title")} />
      <textarea className={inputClass} placeholder="Summary of the finding (50+ characters)" required minLength={50} rows={4} value={form.abstract} onChange={set("abstract")} />
      <input className={inputClass} placeholder="Method (e.g. household survey, DiD)" value={form.method} onChange={set("method")} />
      <select className={inputClass} value={form.finding_direction} onChange={set("finding_direction")} aria-label="Direction">
        <option value="">Direction of effect (optional)</option>
        {FINDING_DIRECTIONS.map((d) => <option key={d}>{d}</option>)}
      </select>
      <FormField label="States (comma separated)"><input className={inputClass} value={form.states} onChange={set("states")} placeholder="Odisha, Assam" /></FormField>
      <FormField label="Themes (comma separated)"><input className={inputClass} value={form.themes} onChange={set("themes")} placeholder="land_records" /></FormField>
      <input className={inputClass} placeholder="Link to paper or data (optional)" value={form.url} onChange={set("url")} />
      <Button className="w-full">Submit for review</Button>
      {confirmation && <p className="text-sm text-ok">{confirmation}</p>}
    </form>
  );
}

export default function Contributions() {
  const { user, hasRole } = useAuth();
  const { data: contributions, reload } = useApi("/api/v1/contributions", undefined, [user.role]);
  const [error, setError] = useState<unknown>(null);
  const isReviewer = hasRole("reviewer");

  async function decide(id: number, approve: boolean) {
    setError(null);
    try {
      await api.post(`/api/v1/contributions/${id}/decide`, { approve });
      reload();
    } catch (x) {
      setError(x);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
      <Card title={isReviewer ? "Review queue and contributions" : "Contributions"}>
        <ErrorAlert error={error} />
        <DataTable rows={contributions ?? []} columns={[
          { key: "title", label: "Title" },
          { key: "kind", label: "Type" },
          { key: "submitter", label: "By", render: (r) => r.submitter ?? "" },
          { key: "status", label: "Status", render: (r) => (
            <Badge tone={r.status === "approved" ? "ok" : r.status === "rejected" ? "danger" : "warn"}>{r.status}</Badge>
          ) },
          { key: "actions", label: "", render: (r) => isReviewer && r.status === "submitted" && (
            <span className="flex gap-1">
              <Button className="text-xs" onClick={() => decide(r.id, true)}>Approve</Button>
              <Button variant="ghost" className="text-xs" onClick={() => decide(r.id, false)}>Reject</Button>
            </span>
          ) },
        ]} />
      </Card>
      <Card title="Submit a finding">
        {user.role === "public"
          ? <p className="text-sm"><SignInLink /> to submit research findings.</p>
          : <SubmitFindingForm onSubmitted={reload} onError={setError} />}
      </Card>
    </div>
  );
}
