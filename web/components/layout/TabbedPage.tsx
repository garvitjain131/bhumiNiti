import { Tabs } from "@/components/ui";
import { useTabQuery } from "@/hooks/useTabQuery";
import { useAuth } from "@/lib/auth/AuthProvider";
import { PageContainer } from "./PageContainer";

export type TabView = { id: string; label: string; view: React.ComponentType; minimumRole?: string };

/** A page whose sections are tabs; the active tab is kept in ?tab= so it can be linked to. */
export function TabbedPage({ title, subtitle, tabs }: { title: string; subtitle?: React.ReactNode; tabs: TabView[] }) {
  const { hasRole } = useAuth();
  const visible = tabs.filter((t) => !t.minimumRole || hasRole(t.minimumRole));
  const [activeId, setActiveId] = useTabQuery(visible.map((t) => t.id));
  const ActiveView = visible.find((t) => t.id === activeId)?.view;

  return (
    <PageContainer title={title} subtitle={subtitle}>
      <Tabs tabs={visible} value={activeId} onChange={setActiveId} />
      {ActiveView && <ActiveView />}
    </PageContainer>
  );
}
