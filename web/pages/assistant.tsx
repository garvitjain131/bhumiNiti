import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { AnswerSections } from "@/components/assistant/AnswerSections";
import { DataFindingsPanel } from "@/components/assistant/DataFindingsPanel";
import { DigitalTwinPanel } from "@/components/assistant/DigitalTwinPanel";
import { DocumentEvidencePanel } from "@/components/assistant/DocumentEvidencePanel";
import { EvidenceGapsPanel } from "@/components/assistant/EvidenceGapsPanel";
import { EvidenceMatrixTable } from "@/components/assistant/EvidenceMatrixTable";
import { ScenarioSettings, type ScenarioChoice } from "@/components/assistant/ScenarioSettings";
import { SourcesPanel } from "@/components/assistant/SourcesPanel";
import { VerificationPanel } from "@/components/assistant/VerificationPanel";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button, ErrorAlert, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api/client";

const EXAMPLES = [
  { kind: "What do we know?", q: "Does digitisation of land records reduce land disputes?" },
  { kind: "What does the data show?", q: "Which districts currently show the highest land conflict risk?" },
  { kind: "What could happen?", q: "What could happen if farmland conversion is restricted by 60% in Maharashtra?" },
  { kind: "All three", q: "What does existing research say about land conflict, which districts currently show the highest risk, and what could happen if conflict-resolution capacity is increased?" },
];
const DETAIL_TABS = [
  { id: "twin", label: "Policy scenario" },
  { id: "data", label: "Data" },
  { id: "documents", label: "Research" },
  { id: "gaps", label: "What is still unknown" },
  { id: "sources", label: "Sources" },
];
const NO_SCENARIO: ScenarioChoice = { lever: null, params: null, routes: null };

export default function ResearchAssistantPage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [scenario, setScenario] = useState<ScenarioChoice>(NO_SCENARIO);
  const [detailTab, setDetailTab] = useState("twin");

  async function ask(q = question, choice: ScenarioChoice = NO_SCENARIO) {
    if (q.trim().length < 5) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.post("/api/v1/assistant/ask", { question: q, ...choice });
      setResult(r);
      setScenario(r.twin?.status === "ok" ? { lever: r.twin.lever, params: r.twin.policy_lever.parameters, routes: choice.routes } : choice);
      setDetailTab(r.twin ? "twin" : r.data ? "data" : r.document ? "documents" : "gaps");
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }

  // A question passed as ?q= (from the overview page or a shared link) is asked straight away.
  useEffect(() => {
    if (!router.isReady || typeof router.query.q !== "string") return;
    setQuestion(router.query.q);
    ask(router.query.q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady]);

  const claimTypes: Record<string, string> = Object.fromEntries((result?.evidence_matrix ?? []).map((c: any) => [c.id, c.type]));

  return (
    <PageContainer title="Research assistant"
      subtitle="Ask any question about land policy in India. You get a cited answer drawn from research, district data and policy scenarios, with a clear note of what is still unknown.">
      <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="mb-3 flex gap-2">
        <input className="flex-1 rounded-md border border-line bg-field px-4 py-3 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20" value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a land-policy research question" aria-label="Question" />
        <button className="rounded-md bg-accent-solid px-5 font-medium text-white hover:brightness-110">Ask</button>
      </form>
      <div className="mb-3 grid gap-2 md:grid-cols-4">
        {EXAMPLES.map((e) => (
          <button key={e.q} onClick={() => { setQuestion(e.q); ask(e.q); }}
            className="rounded-md border border-line bg-panel p-2 text-left text-xs hover:border-accent">
            <span className="block font-semibold text-accent">{e.kind}</span>{e.q}
          </button>
        ))}
      </div>
      <div className="mb-6">
        <Button variant="ghost" className="text-xs" onClick={() => setShowSettings(!showSettings)} aria-expanded={showSettings}>
          {showSettings ? "Hide" : "Show"} scenario settings
        </Button>
        {showSettings && (
          <div className="mt-2">
            <ScenarioSettings initial={scenario} onApply={(c) => { setScenario(c); ask(question, c); }} />
          </div>
        )}
      </div>

      <ErrorAlert error={error} />
      {busy && <Spinner text="Finding the evidence and preparing your answer" />}
      {result && (
        <div className="space-y-4">
          {result.insufficient_evidence && (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">{result.answer}</p>
          )}
          <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
            <AnswerSections sections={result.answer_sections} claimTypes={claimTypes} synthesis={result.synthesis} />
            <VerificationPanel checks={result.verification} />
          </div>
          <EvidenceMatrixTable claims={result.evidence_matrix} runId={result.twin?.run?.run_id} />
          <div>
            <Tabs tabs={DETAIL_TABS} value={detailTab} onChange={setDetailTab} />
            {detailTab === "twin" && <DigitalTwinPanel twin={result.twin} />}
            {detailTab === "data" && <DataFindingsPanel data={result.data} />}
            {detailTab === "documents" && <DocumentEvidencePanel document={result.document} />}
            {detailTab === "gaps" && <EvidenceGapsPanel gaps={result.evidence_gaps} question={result.question} />}
            {detailTab === "sources" && <SourcesPanel sources={result.sources} />}
          </div>
        </div>
      )}
    </PageContainer>
  );
}
