import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, ErrorAlert, Spinner, inputClass } from "@/components/ui";
import { CALL_KIND_LABELS } from "@/config/innovation";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";

const EMPTY_CALL = { kind: "hackathon", title: "", description: "", theme: "", budget_lakh: "", closes: "" };

function NewCallForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState(EMPTY_CALL);
  const [error, setError] = useState<unknown>(null);

  async function createCall(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/v1/calls", { ...form, budget_lakh: form.budget_lakh ? Number(form.budget_lakh) : null, closes: form.closes || null });
      onCreated();
    } catch (x) {
      setError(x);
    }
  }

  return (
    <Card title="New call">
      <form onSubmit={createCall} className="space-y-2">
        <select className={inputClass} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          {Object.entries(CALL_KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input className={inputClass} placeholder="Title" required minLength={5} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <textarea className={inputClass} placeholder="Description" required minLength={20} rows={3} value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <input className={inputClass} placeholder="Theme" value={form.theme} onChange={(e) => setForm({ ...form, theme: e.target.value })} />
        <div className="grid grid-cols-2 gap-2">
          <input className={inputClass} placeholder="Budget (lakh)" type="number" value={form.budget_lakh} onChange={(e) => setForm({ ...form, budget_lakh: e.target.value })} />
          <input className={inputClass} type="date" value={form.closes} onChange={(e) => setForm({ ...form, closes: e.target.value })} aria-label="Closes" />
        </div>
        <ErrorAlert error={error} />
        <Button className="w-full">Publish call</Button>
      </form>
    </Card>
  );
}

export default function CallsList() {
  const { data: calls, reload } = useApi("/api/v1/calls");
  const { data: schemes } = useApi("/api/v1/calls/schemes");
  const { hasRole } = useAuth();
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <div className="space-y-3">
        {!calls ? <Spinner /> : calls.map((c: any) => (
          <Card key={c.id}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{CALL_KIND_LABELS[c.kind]}</Badge>
              <Badge tone={c.status === "open" ? "ok" : c.status === "draft" ? "warn" : "neutral"}>{c.status}</Badge>
              {c.source_gap && <Badge>from Gap Radar</Badge>}
            </div>
            <Link href={`/calls/${c.id}`} className="mt-1 block text-lg" style={{ fontFamily: "var(--font-serif)" }}>{c.title}</Link>
            <p className="mt-1 line-clamp-2 text-sm text-muted">{c.description}</p>
            <p className="mt-1 text-xs text-muted">
              {c.budget_lakh ? `Up to Rs ${c.budget_lakh} lakh · ` : ""}closes {c.closes ?? "–"} · {c.applications} applications
            </p>
          </Card>
        ))}
      </div>
      <div className="space-y-4">
        {schemes && (
          <Card title="DoLR research grant schemes">
            {Object.values(schemes.dolr_grant_schemes).map((s: any) => (
              <p key={s.name} className="text-sm"><b>{s.name}</b>: {s.per_year}/year, up to Rs {s.max_lakh} lakh, {s.years} years</p>
            ))}
            <p className="mt-2 text-xs text-muted">
              Workflow: {schemes.grant_stages.join(" → ")}. Funds: {schemes.disbursement.map((d: any) => `${d.pct}% ${d.note}`).join("; ")}.
            </p>
          </Card>
        )}
        {hasRole("official") && <NewCallForm onCreated={reload} />}
      </div>
    </div>
  );
}
