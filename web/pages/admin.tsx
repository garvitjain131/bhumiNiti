import ApiKeys from "@/components/admin/ApiKeys";
import AuditLog from "@/components/admin/AuditLog";
import UsersRoles from "@/components/admin/UsersRoles";
import { PageContainer } from "@/components/layout/PageContainer";
import { TabbedPage } from "@/components/layout/TabbedPage";
import { ErrorAlert, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth/AuthProvider";

const TITLE = "Administration";
const TABS = [
  { id: "audit-log", label: "Audit log", view: AuditLog },
  { id: "users", label: "Users & roles", view: UsersRoles, minimumRole: "admin" },
  { id: "api-keys", label: "API keys", view: ApiKeys, minimumRole: "admin" },
];

export default function AdminPage() {
  const { user, ready } = useAuth();
  if (!ready) return <PageContainer title={TITLE}><Spinner /></PageContainer>;
  if (!["admin", "official"].includes(user.role)) {
    return <PageContainer title={TITLE}><ErrorAlert error={{ status: 403, message: "administrators and officials only" }} /></PageContainer>;
  }
  return (
    <TabbedPage
      title={TITLE}
      subtitle="Roles, partner access and the tamper-evident audit trail. Access requests for restricted data are handled under Data & APIs."
      tabs={TABS}
    />
  );
}
