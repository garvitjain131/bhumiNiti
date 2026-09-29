import { Badge, Card, DataTable } from "@/components/ui";
import { useApi } from "@/hooks/useApi";

export default function PilotRegistry() {
  const { data } = useApi("/api/v1/pilots");
  return (
    <Card title="Pilot registry">
      <DataTable rows={data ?? []} empty="No pilots yet." columns={[
        { key: "title", label: "Pilot" },
        { key: "state", label: "State" },
        { key: "lead", label: "Lead" },
        { key: "status", label: "Status", render: (r) => <Badge tone={r.status === "completed" ? "ok" : "accent"}>{r.status}</Badge> },
        { key: "start_date", label: "Started" },
        { key: "outcomes", label: "Outcomes", align: "right" },
      ]} />
    </Card>
  );
}
