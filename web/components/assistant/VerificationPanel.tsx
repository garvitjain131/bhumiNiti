import { Badge, Card } from "@/components/ui";
import { STATUS_TONE } from "./evidenceTypes";

/** Checks run before synthesis: source, data and simulation support, assumptions, contradictions, sufficiency, causality. */
export function VerificationPanel({ checks }: { checks: any[] }) {
  return (
    <Card title="Evidence verification">
      <ul className="space-y-2 text-sm">
        {checks.map((c) => (
          <li key={c.check} className="flex items-start gap-2">
            <Badge tone={STATUS_TONE[c.status] ?? "neutral"}>{c.status}</Badge>
            <span><b>{c.check}.</b> <span className="text-muted">{c.detail}</span></span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
