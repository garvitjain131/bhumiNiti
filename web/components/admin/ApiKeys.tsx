import { useState } from "react";
import { Badge, Button, Card, DataTable, inputClass } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";

/** Issue and revoke API keys for partner systems. A new key is shown once only. */
export default function ApiKeys() {
  const { data: keys, reload } = useApi("/api/v1/admin/api-keys");
  const [partnerName, setPartnerName] = useState("");
  const [issuedKey, setIssuedKey] = useState<any>(null);

  async function issueKey(e: React.FormEvent) {
    e.preventDefault();
    setIssuedKey(await api.post("/api/v1/admin/api-keys", { name: partnerName }));
    setPartnerName("");
    reload();
  }

  async function revoke(id: number) {
    await api.del(`/api/v1/admin/api-keys/${id}`);
    reload();
  }

  return (
    <Card title="Partner API keys">
      <form className="mb-3 flex gap-2" onSubmit={issueKey}>
        <input className={inputClass} placeholder="Partner system, e.g. Odisha Land Stack" required minLength={3} value={partnerName}
          onChange={(e) => setPartnerName(e.target.value)} />
        <Button>Issue key</Button>
      </form>
      {issuedKey && (
        <p className="mb-3 rounded bg-amber-50 p-2 text-sm">Copy this key now; it is not shown again: <code className="break-all">{issuedKey.key}</code></p>
      )}
      <DataTable rows={keys ?? []} columns={[
        { key: "name", label: "Partner" },
        { key: "created_at", label: "Issued" },
        { key: "active", label: "Status", render: (k) => <Badge tone={k.active ? "ok" : "neutral"}>{k.active ? "active" : "revoked"}</Badge> },
        { key: "actions", label: "", render: (k) => k.active ? <Button variant="ghost" className="text-xs" onClick={() => revoke(k.id)}>Revoke</Button> : null },
      ]} />
    </Card>
  );
}
