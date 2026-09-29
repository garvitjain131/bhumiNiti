import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { EvidenceListItem } from "@/components/evidence/EvidenceListItem";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge, Card, ErrorAlert, Spinner, Tabs, inputClass } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";
import { toTitleCase } from "@/lib/format";

type Mode = "search" | "browse";
type Filters = Record<"type_group" | "state" | "theme" | "source" | "year_from", string>;

function FacetSelect({ label, value, options, onChange, formatOption = (k) => k }: {
  label: string; value: string; options?: { key: string; n: number }[]; onChange: (v: string) => void; formatOption?: (k: string) => string;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      <select className={inputClass} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {(options ?? []).map((o) => <option key={o.key} value={o.key}>{formatOption(String(o.key))} ({o.n})</option>)}
      </select>
    </label>
  );
}

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("browse");
  const [filters, setFilters] = useState<Filters>({ type_group: "", state: "", theme: "", source: "", year_from: "" });
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const { data: facets } = useApi("/api/v1/evidence/facets");

  // Read ?q= and ?type_group= once the router has the query string.
  useEffect(() => {
    if (!router.isReady) return;
    const q = typeof router.query.q === "string" ? router.query.q : "";
    const typeGroup = typeof router.query.type_group === "string" ? router.query.type_group : "";
    setQuery(q);
    setMode(q ? "search" : "browse");
    if (typeGroup) setFilters((f) => ({ ...f, type_group: typeGroup }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady]);

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "search" && query.trim().length > 1) {
        setResults(await api.get("/api/v1/evidence/search", { q: query, ...filters, limit: 30 }));
      } else {
        const rows = await api.get("/api/v1/evidence/browse", { ...filters, limit: 40 });
        setResults({ results: rows, total: rows.length, mode: "browse" });
      }
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (router.isReady) runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, mode, filters]);

  const setFilter = (key: keyof Filters) => (value: string) => setFilters({ ...filters, [key]: value });

  return (
    <PageContainer title="Search & repository"
      subtitle="Research papers, policy reports, legal and government documents, datasets and case studies in one place. Search by question, not keyword: results combine keyword matching with semantic similarity.">
      <Tabs value={mode} onChange={(m) => setMode(m as Mode)} tabs={[{ id: "search", label: "Search" }, { id: "browse", label: "Browse the repository" }]} />
      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <Card title="Filters">
          <div className="space-y-3">
            <FacetSelect label="Document type" value={filters.type_group} options={facets?.type_group} onChange={setFilter("type_group")} />
            <FacetSelect label="State mentioned" value={filters.state} options={facets?.state} onChange={setFilter("state")} />
            <FacetSelect label="Theme" value={filters.theme} options={facets?.theme} onChange={setFilter("theme")} formatOption={toTitleCase} />
            <FacetSelect label="Source" value={filters.source} options={facets?.source} onChange={setFilter("source")} formatOption={toTitleCase} />
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-muted">Published from year</span>
              <input className={inputClass} type="number" min={1950} max={2030} value={filters.year_from}
                onChange={(e) => setFilter("year_from")(e.target.value)} />
            </label>
          </div>
        </Card>
        <div>
          {mode === "search" && (
            <form onSubmit={runSearch} className="mb-4 flex gap-2">
              <input className="flex-1 rounded-md border border-line bg-field px-4 py-2 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20" value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. how does land pooling affect farmers' incomes" aria-label="Search query" />
              <button className="rounded-md bg-accent-solid px-4 font-medium text-white hover:brightness-110">Search</button>
            </form>
          )}
          <ErrorAlert error={error} />
          {busy ? <Spinner /> : results && (
            <Card title={`${results.total} results`} right={results.mode && <Badge>{results.mode}</Badge>}>
              {results.contributions?.length > 0 && (
                <div className="mb-3 rounded-md bg-accent-soft p-3 text-sm">
                  <div className="mb-1 font-medium">New platform contributions (reviewed)</div>
                  {results.contributions.map((c: any) => <div key={c.evidence_id}>{c.title}</div>)}
                </div>
              )}
              {results.results.map((r: any) => <EvidenceListItem key={r.evidence_id} item={r} />)}
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
