import { useState } from "react";
import { Badge, Card, DataTable, ErrorAlert } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";

const ASSIGNABLE_ROLES = ["researcher", "institution_admin", "reviewer", "official", "admin"];

export default function UsersRoles() {
  const { data: users, reload, error } = useApi("/api/v1/admin/users");
  const [updateError, setUpdateError] = useState<unknown>(null);

  async function changeRole(user: any, role: string) {
    setUpdateError(null);
    try {
      await api.patch(`/api/v1/admin/users/${user.id}`, { role, active: !!user.active });
      reload();
    } catch (x) {
      setUpdateError(x);
    }
  }

  return (
    <Card title="Users and roles">
      <ErrorAlert error={error ?? updateError} />
      <DataTable rows={users ?? []} columns={[
        { key: "name", label: "Name" },
        { key: "email", label: "Email" },
        { key: "institution", label: "Institution" },
        { key: "role", label: "Role", render: (u) => (
          <select className="rounded border border-line text-sm" value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
            {ASSIGNABLE_ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>
        ) },
        { key: "active", label: "Active", render: (u) => <Badge tone={u.active ? "ok" : "danger"}>{u.active ? "yes" : "no"}</Badge> },
      ]} />
    </Card>
  );
}
