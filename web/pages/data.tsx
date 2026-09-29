import ApiConnectors from "@/components/data/ApiConnectors";
import DatasetCatalog from "@/components/data/DatasetCatalog";
import LandRecords from "@/components/data/LandRecords";
import { TabbedPage } from "@/components/layout/TabbedPage";

const TABS = [
  { id: "catalog", label: "Dataset catalogue", view: DatasetCatalog },
  { id: "apis", label: "APIs & connectors", view: ApiConnectors },
  { id: "land-records", label: "Land records: access & anonymisation", view: LandRecords },
];

export default function DataPage() {
  return (
    <TabbedPage
      title="Data & APIs"
      subtitle="What the platform holds, where each file came from, and how other systems connect. Parcel-level land records are shown only as a synthetic demonstration of role-based access and anonymisation."
      tabs={TABS}
    />
  );
}
