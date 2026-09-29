import { Card, DataLabel, DataTable } from "@/components/ui";
import { useApi } from "@/hooks/useApi";

export default function ModelRegistry() {
  const { data } = useApi("/api/v1/analytics/models");
  return (
    <Card title="Model registry">
      <DataTable rows={data ?? []} columns={[
        { key: "id", label: "Model" },
        { key: "purpose", label: "Purpose" },
        { key: "method", label: "Method" },
        { key: "data", label: "Data" },
        { key: "output_label", label: "Output", render: (r) => <DataLabel label={r.output_label} /> },
        { key: "limitations", label: "Limitations" },
      ]} />
    </Card>
  );
}
