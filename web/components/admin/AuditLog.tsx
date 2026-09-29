import { Button, Card, DataTable, ErrorAlert, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/lib/auth/AuthProvider";

/** Officials see only whether the hash chain is intact; administrators also see the entries. */
export default function AuditLog() {
  const { user } = useAuth();
  const isAdmin = user.role === "admin";
  const { data: chain, reload: reverify } = useApi("/api/v1/audit/verify");
  const { data: entries, error, reload } = useApi(isAdmin ? "/api/v1/audit" : null, { limit: 150 });

  if (!isAdmin) {
    return (
      <Card title="Audit chain">
        {!chain ? <Spinner /> : (
          <p className={`text-sm ${chain.valid ? "text-ok" : "text-danger"}`}>
            {chain.valid ? `Intact: ${chain.entries_checked} entries.` : `Broken at ${chain.broken_at_id}.`} Full log: administrators only.
          </p>
        )}
      </Card>
    );
  }

  return (
    <Card title="Tamper-evident audit log" right={<Button variant="ghost" onClick={() => { reverify(); reload(); }}>Re-verify</Button>}>
      {chain && (
        <p className={`mb-3 text-sm ${chain.valid ? "text-ok" : "text-danger"}`}>
          {chain.valid
            ? `Hash chain intact: ${chain.entries_checked} entries verified (head ${chain.head_hash?.slice(0, 16)}…).`
            : `Chain broken at entry ${chain.broken_at_id}.`}
        </p>
      )}
      <ErrorAlert error={error} />
      <DataTable rows={entries ?? []} columns={[
        { key: "ts", label: "Time", render: (r) => <span className="text-xs">{r.ts}</span> },
        { key: "user_email", label: "User", render: (r) => r.user_email ?? "public" },
        { key: "action", label: "Action" },
        { key: "resource", label: "Resource", render: (r) => <span className="text-xs">{r.resource}</span> },
        { key: "detail", label: "Detail", render: (r) => <span className="line-clamp-1 max-w-xs text-xs text-muted">{r.detail}</span> },
        { key: "hash", label: "Hash", render: (r) => <span className="font-mono text-xs">{r.hash.slice(0, 10)}…</span> },
      ]} />
    </Card>
  );
}
