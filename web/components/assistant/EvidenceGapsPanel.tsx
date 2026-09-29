import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, ErrorAlert } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { SEVERITY_TONE } from "./evidenceTypes";

const RESEARCH_LOOP = ["Evidence gap", "Research requirement", "Research call", "Application", "Review", "Award", "Pilot", "Outcome", "New evidence", "Better digital twin"];

/** What is missing and why it matters; officials can turn a gap into a draft research call. */
export function EvidenceGapsPanel({ gaps, question }: { gaps: any[]; question: string }) {
  const { hasRole } = useAuth();
  const [drafted, setDrafted] = useState<Record<number, number>>({});
  const [error, setError] = useState<unknown>(null);

  async function draftCall(gap: any, index: number) {
    setError(null);
    try {
      const call = await api.post("/api/v1/calls", {
        kind: "institutional_grant", status: "draft", theme: gap.kind,
        title: `Research requirement: ${(gap.research_requirement ?? gap.what).slice(0, 150)}`,
        description: `Evidence gap found by the research assistant.\n\nQuestion: ${question}\n\nWhat is missing: ${gap.what}\n\n` +
          `Why it matters: ${gap.why}` + (gap.research_requirement ? `\n\nResearch requirement: ${gap.research_requirement}` : "") +
          "\n\nFindings and data will be deposited on the platform and used to improve the policy scenarios.",
      });
      setDrafted({ ...drafted, [index]: call.id });
    } catch (e) {
      setError(e);
    }
  }

  return (
    <Card title="Evidence gaps: what we still do not know">
      <ol className="mb-3 flex flex-wrap items-center gap-1 text-xs text-muted" aria-label="Research loop">
        {RESEARCH_LOOP.map((s, i) => <li key={s}>{s}{i < RESEARCH_LOOP.length - 1 && " →"}</li>)}
      </ol>
      <ErrorAlert error={error} />
      {gaps.length === 0 ? <p className="text-sm text-muted">No major gap detected.</p> : (
        <ul className="space-y-3 text-sm">
          {gaps.map((g, i) => (
            <li key={i} className="border-b border-line/60 pb-2 last:border-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={SEVERITY_TONE[g.severity] ?? "neutral"}>{g.severity}</Badge>
                <Badge>{g.kind.replace(/_/g, " ")}</Badge>
              </div>
              <p className="mt-1"><b>{g.what}</b></p>
              <p className="text-muted">Why it matters: {g.why}</p>
              {g.research_requirement && <p className="text-accent">Research requirement: {g.research_requirement}</p>}
              {hasRole("official") && (
                drafted[i]
                  ? <Link href={`/calls/${drafted[i]}`} className="text-xs">Draft call #{drafted[i]} created: review and publish →</Link>
                  : <Button variant="ghost" className="mt-1 text-xs" onClick={() => draftCall(g, i)}>Draft a research call</Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted">
        Gaps feed the <Link href="/innovation">Innovation Portal</Link>: calls → applications → review → award → pilot → reported outcomes,
        which return to the repository as new evidence.
      </p>
    </Card>
  );
}
