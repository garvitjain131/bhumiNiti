import EmergingTrends from "@/components/analytics/EmergingTrends";
import ModelRegistry from "@/components/analytics/ModelRegistry";
import PolicyEvaluation from "@/components/analytics/PolicyEvaluation";
import TrendsForecasts from "@/components/analytics/TrendsForecasts";
import { TabbedPage } from "@/components/layout/TabbedPage";

const TABS = [
  { id: "trends", label: "Trends & forecasts", view: TrendsForecasts },
  { id: "policy-evaluation", label: "Policy evaluation", view: PolicyEvaluation },
  { id: "emerging-trends", label: "Emerging trends & correlation", view: EmergingTrends },
  { id: "model-registry", label: "Model registry", view: ModelRegistry },
];

export default function AnalyticsPage() {
  return (
    <TabbedPage
      title="Analytics & decision support"
      subtitle="Trends, forecasts with back-tests, policy evaluation, emerging trends and anomalies. Each result states whether it is descriptive, correlational, predicted or simulated."
      tabs={TABS}
    />
  );
}
