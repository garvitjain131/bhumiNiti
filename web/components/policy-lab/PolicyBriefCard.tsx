import { useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { api } from "@/lib/api/client";

/** Exported brief with its SHA-256; "Verify" checks the (possibly edited) text against the hash and the audit log. */
export function PolicyBriefCard({ brief, runId }: { brief: { markdown: string; sha256: string }; runId: number }) {
  const [text, setText] = useState(brief.markdown);
  const [verification, setVerification] = useState<any>(null);

  function download() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    a.download = `policy-brief-run-${runId}.md`;
    a.click();
  }

  async function verify() {
    setVerification(await api.post("/api/v1/simulations/verify-brief", { markdown: text }));
  }

  return (
    <Card title="Policy brief" right={<Badge tone="ok">SHA-256 {brief.sha256.slice(0, 12)}…</Badge>}>
      <textarea className="h-72 w-full rounded-md border border-line bg-field p-2 font-mono text-xs" value={text}
        onChange={(e) => setText(e.target.value)} aria-label="Brief" />
      <div className="mt-2 flex gap-2">
        <Button variant="ghost" onClick={download}>Download .md</Button>
        <Button onClick={verify}>Verify (edit the text first to see tampering detected)</Button>
      </div>
      {verification && (
        <p className={`mt-2 text-sm ${verification.hash_matches_content ? "text-ok" : "text-danger"}`}>
          {verification.hash_matches_content && verification.found_in_audit_log
            ? `Verified: unaltered, issued ${verification.issued?.ts} and recorded in the tamper-evident audit log.`
            : "Not verified: the text does not match its hash (altered after export)."}
        </p>
      )}
    </Card>
  );
}
