import CallsList from "@/components/innovation/CallsList";
import Contributions from "@/components/innovation/Contributions";
import GapRadar from "@/components/innovation/GapRadar";
import PilotRegistry from "@/components/innovation/PilotRegistry";
import { TabbedPage } from "@/components/layout/TabbedPage";

const TABS = [
  { id: "gap-radar", label: "Gap Radar", view: GapRadar },
  { id: "calls", label: "Calls: grants, hackathons, pilots", view: CallsList },
  { id: "pilots", label: "Pilot registry", view: PilotRegistry },
  { id: "contributions", label: "Submit & review findings", view: Contributions },
];

export default function InnovationPage() {
  return (
    <TabbedPage
      title="Innovation portal"
      subtitle="From evidence gaps to funded research: grant calls that follow DoLR's schemes, hackathons, pilots and competitions. Pilot outcomes and researcher findings flow back into the evidence base after review."
      tabs={TABS}
    />
  );
}
