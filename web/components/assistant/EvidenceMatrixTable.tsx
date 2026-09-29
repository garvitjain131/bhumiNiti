import Link from "next/link";
import { Badge, Card, DataLabel } from "@/components/ui";
import { EVIDENCE_TYPES, STATUS_TONE, claimAnchor } from "./evidenceTypes";

function EvidenceRef({ e, runId }: { e: any; runId?: number }) {
  if (e.kind === "source") return <Link href={`/evidence/${encodeURIComponent(e.ref)}`} className="block truncate">{e.title}</Link>;
  if (e.kind === "model") return <Link href={runId ? `/policy-lab?run=${runId}` : "/policy-lab"} className="block">{e.title} <span className="text-muted">({e.ref})</span></Link>;
  return <span className="block">{e.title} <span className="font-mono text-muted">{e.ref}</span></span>;
}

/** Every claim in the answer with its evidence, type, support and verification status. */
export function EvidenceMatrixTable({ claims, runId }: { claims: any[]; runId?: number }) {
  return (
    <Card title="Evidence matrix">
      {claims.length === 0 ? <p className="text-sm text-muted">No verified claims.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-2 py-2">#</th><th className="px-2 py-2">Claim</th><th className="px-2 py-2">Evidence</th>
                <th className="px-2 py-2">Type</th><th className="px-2 py-2">Support</th><th className="px-2 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c) => {
                const style = EVIDENCE_TYPES[c.type] ?? EVIDENCE_TYPES.overview;
                return (
                  <tr key={c.id} id={claimAnchor(c.id)} className="scroll-mt-4 border-b border-line/60 align-top last:border-0 target:bg-amber-50">
                    <td className="px-2 py-1.5"><span className={`rounded border px-1 text-[11px] font-semibold ${style.chip}`}>{c.id}</span></td>
                    <td className="max-w-md px-2 py-1.5">{c.claim}</td>
                    <td className="max-w-[16rem] px-2 py-1.5 text-xs">{c.evidence.map((e: any, i: number) => <EvidenceRef key={i} e={e} runId={runId} />)}</td>
                    <td className="px-2 py-1.5 text-xs"><div>{style.label}</div><DataLabel label={c.label} /></td>
                    <td className="max-w-[14rem] px-2 py-1.5 text-xs text-muted">{c.support}</td>
                    <td className="px-2 py-1.5"><Badge tone={STATUS_TONE[c.status] ?? "neutral"}>{c.status}</Badge></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-xs text-muted">
        Verified = checked against its source or re-read from the data; simulated = produced by the scenario model under the listed
        assumptions; assumption = a model input without direct evidence; correlational = association only.
      </p>
    </Card>
  );
}
