import { Card } from "@/components/ui";
import { EVIDENCE_TYPES, claimAnchor } from "./evidenceTypes";

function CitationChip({ id, type }: { id: string; type: string }) {
  const style = EVIDENCE_TYPES[type] ?? EVIDENCE_TYPES.overview;
  return (
    <a href={`#${claimAnchor(id)}`} className={`ml-1 inline-block rounded border px-1 text-[11px] font-semibold no-underline ${style.chip}`}
      title={`${style.label}: open ${id} in the evidence matrix`}>
      {id}
    </a>
  );
}

/** The cited final answer: one block per section, each sentence marked with the kind of evidence behind it. */
export function AnswerSections({ sections, claimTypes, synthesis }: {
  sections: any[]; claimTypes: Record<string, string>; synthesis: any;
}) {
  return (
    <Card title="Answer">
      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        {["document", "analytics", "simulation", "assumption", "gap"].map((t) => (
          <span key={t} className="flex items-center gap-1">
            <span className={`inline-block h-2 w-2 rounded-full ${EVIDENCE_TYPES[t].dot}`} /> {EVIDENCE_TYPES[t].label}
          </span>
        ))}
      </div>
      <div className="space-y-4">
        {sections.map((section) => (
          <section key={section.key}>
            <h3 className="mb-1 text-sm font-semibold">{section.title}</h3>
            <ul className="space-y-1.5 text-sm leading-relaxed">
              {section.sentences.map((s: any, i: number) => {
                const style = EVIDENCE_TYPES[s.type] ?? EVIDENCE_TYPES.overview;
                return (
                  <li key={i} className="flex gap-2">
                    <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${style.dot}`} aria-label={style.label} />
                    <span>
                      {s.text}
                      {s.cites.map((c: string) => <CitationChip key={c} id={c} type={claimTypes[c] ?? s.type} />)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      {synthesis.dropped > 0 && (
        <p className="mt-3 text-xs text-muted">{synthesis.dropped} LLM sentence(s) were dropped because they cited no claim or stated a number not in the evidence matrix.</p>
      )}
      {synthesis.llm_error && <p className="mt-3 text-xs text-muted">LLM wording unavailable ({synthesis.llm_error}); template synthesis used.</p>}
    </Card>
  );
}
