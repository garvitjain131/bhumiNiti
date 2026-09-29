import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge, Button, Card, ErrorAlert, FormField, Spinner, inputClass } from "@/components/ui";
import { APPLICATION_STAGES } from "@/config/innovation";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";

type Review = { score: string; comments: string; coi: boolean };
const stageLabel = (s: string) => s.replace("_", " ");

export default function CallDetailPage() {
  const router = useRouter();
  const callId = typeof router.query.id === "string" ? router.query.id : null;
  const { user, hasRole } = useAuth();
  const { data: call, error, reload } = useApi(callId && `/api/v1/calls/${callId}`, undefined, [user.role]);
  const [application, setApplication] = useState({ title: "", hypothesis: "", methodology: "", budget_lakh: "" });
  const [reviews, setReviews] = useState<Record<number, Review>>({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");

  const run = async (action: () => Promise<void>) => {
    setActionError(null);
    try {
      await action();
      reload();
    } catch (e) {
      setActionError(e);
    }
  };
  const setReview = (appId: number, patch: Partial<Review>) => setReviews({ ...reviews, [appId]: { ...reviews[appId], ...patch } });

  if (error) return <PageContainer title="Call"><ErrorAlert error={error} /></PageContainer>;
  if (!call) return <PageContainer title="Call"><Spinner /></PageContainer>;
  const canReview = hasRole("reviewer") && user.role !== "official";

  return (
    <PageContainer title={call.title}
      subtitle={
        <span className="flex flex-wrap gap-2">
          <Link href="/innovation?tab=calls">← All calls</Link>
          <Badge tone="accent">{stageLabel(call.kind)}</Badge>
          <Badge tone={call.status === "open" ? "ok" : "warn"}>{call.status}</Badge>
          {call.budget_lakh && <span>Up to Rs {call.budget_lakh} lakh</span>}
          <span>closes {call.closes ?? "–"}</span>
        </span>
      }
      actions={hasRole("official") && call.status !== "open"
        ? <Button onClick={() => run(async () => { await api.post(`/api/v1/calls/${callId}/status?status=open`); })}>Publish (open)</Button>
        : undefined}>
      <ErrorAlert error={actionError} />
      {notice && <p className="mb-3 rounded-md bg-accent-soft p-2 text-sm">{notice}</p>}
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card title="Call text"><p className="whitespace-pre-line text-sm">{call.description}</p></Card>
          <Card title={`Applications (${call.applications.length})`}>
            {call.applications.length === 0 && (
              <p className="text-sm text-muted">{hasRole("reviewer") ? "No applications yet." : "Your applications to this call appear here."}</p>
            )}
            {call.applications.map((a: any) => (
              <div key={a.id} className="mb-4 border-b border-line pb-3 last:border-0">
                <div className="flex flex-wrap items-center gap-2">
                  <b>{a.title}</b>
                  <Badge>{stageLabel(a.stage)}</Badge>
                  {a.avg_score !== null && <Badge tone="accent">score {a.avg_score} ({a.reviews} reviews)</Badge>}
                </div>
                <p className="text-xs text-muted">{a.applicant} · {a.institution ?? ""} · Rs {a.budget_lakh} lakh</p>
                <p className="mt-1 text-sm"><b>Hypothesis:</b> {a.hypothesis}</p>
                <p className="text-sm"><b>Method:</b> {a.methodology}</p>
                {canReview && a.stage !== "rejected" && (
                  <div className="mt-2 grid gap-2 rounded-md bg-subtle p-2 md:grid-cols-[90px_1fr_auto_auto]">
                    <input className={inputClass} type="number" min={0} max={100} placeholder="Score" value={reviews[a.id]?.score ?? ""}
                      onChange={(e) => setReview(a.id, { score: e.target.value })} />
                    <input className={inputClass} placeholder="Referee comments" value={reviews[a.id]?.comments ?? ""}
                      onChange={(e) => setReview(a.id, { comments: e.target.value })} />
                    <label className="flex items-center gap-1 text-xs">
                      <input type="checkbox" checked={!!reviews[a.id]?.coi} onChange={(e) => setReview(a.id, { coi: e.target.checked })} />conflict of interest
                    </label>
                    <Button onClick={() => run(async () => {
                      const r = await api.post(`/api/v1/applications/${a.id}/reviews`, {
                        score: Number(reviews[a.id]?.score), comments: reviews[a.id]?.comments ?? "", conflict_of_interest: !!reviews[a.id]?.coi,
                      });
                      setNotice(r.conflict_of_interest_recorded
                        ? "Review saved; conflict of interest recorded, so it is excluded from the average."
                        : "Review saved.");
                    })}>Score</Button>
                  </div>
                )}
                {hasRole("official") && (
                  <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
                    <span className="text-muted">Move to:</span>
                    {[...APPLICATION_STAGES, "rejected"].map((stage) => (
                      <button key={stage} disabled={stage === a.stage}
                        className={`rounded border px-2 py-0.5 ${stage === a.stage ? "border-accent bg-accent-soft" : "border-line"}`}
                        onClick={() => run(async () => {
                          const r = await api.post(`/api/v1/applications/${a.id}/advance?to=${stage}`);
                          setNotice(`Stage: ${stage}. Funds released so far: ${r.funds_released_pct}%.${stage === "awarded" ? " A pilot record was created." : ""}`);
                        })}>
                        {stageLabel(stage)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </Card>
        </div>
        <Card title="Apply">
          {call.status !== "open" ? <p className="text-sm text-muted">This call is not open for applications.</p>
            : user.role === "public" ? <p className="text-sm">Sign in as a researcher to apply.</p> : (
              <form className="space-y-2" onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  await api.post(`/api/v1/calls/${callId}/applications`, { ...application, budget_lakh: Number(application.budget_lakh) });
                  setNotice("Application submitted.");
                });
              }}>
                <input className={inputClass} placeholder="Project title" required minLength={5} value={application.title}
                  onChange={(e) => setApplication({ ...application, title: e.target.value })} />
                <FormField label="Hypothesis">
                  <textarea className={inputClass} required minLength={20} rows={3} value={application.hypothesis}
                    onChange={(e) => setApplication({ ...application, hypothesis: e.target.value })} />
                </FormField>
                <FormField label="Methodology">
                  <textarea className={inputClass} required minLength={20} rows={3} value={application.methodology}
                    onChange={(e) => setApplication({ ...application, methodology: e.target.value })} />
                </FormField>
                <FormField label="Budget (Rs lakh)">
                  <input className={inputClass} type="number" required min={0.1} step={0.1} value={application.budget_lakh}
                    onChange={(e) => setApplication({ ...application, budget_lakh: e.target.value })} />
                </FormField>
                <Button className="w-full">Submit application</Button>
              </form>
            )}
        </Card>
      </div>
    </PageContainer>
  );
}
