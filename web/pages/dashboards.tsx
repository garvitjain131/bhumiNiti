import ClimateResilience from "@/components/dashboards/ClimateResilience";
import GeospatialInsights from "@/components/dashboards/GeospatialInsights";
import LandDisputes from "@/components/dashboards/LandDisputes";
import LandUseTrends from "@/components/dashboards/LandUseTrends";
import PolicyPerformance from "@/components/dashboards/PolicyPerformance";
import ProjectOutcomes from "@/components/dashboards/ProjectOutcomes";
import ResearchOutputs from "@/components/dashboards/ResearchOutputs";
import { TabbedPage } from "@/components/layout/TabbedPage";

const TABS = [
  { id: "research", label: "Research outputs", view: ResearchOutputs },
  { id: "policy-performance", label: "Policy performance", view: PolicyPerformance },
  { id: "land-use", label: "Land-use trends", view: LandUseTrends },
  { id: "climate-resilience", label: "Climate resilience", view: ClimateResilience },
  { id: "land-disputes", label: "Land disputes", view: LandDisputes },
  { id: "project-outcomes", label: "Project outcomes", view: ProjectOutcomes },
  { id: "geospatial", label: "Geospatial insights", view: GeospatialInsights },
];

export default function DashboardsPage() {
  return (
    <TabbedPage
      title="Dashboards"
      subtitle="Every figure shows its source and whether it is observed, estimated from satellite data, simulated or predicted. Hover a KPI for its definition."
      tabs={TABS}
    />
  );
}
