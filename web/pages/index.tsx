import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";
import { DistrictLink } from "@/components/dashboards/DistrictLink";
import { Icon, type IconName } from "@/components/layout/Icon";
import { LandCoverStrip } from "@/components/overview/LandCoverStrip";
import { Card, DataLabel, DataTable, KpiCard, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { formatNumber, toTitleCase } from "@/lib/format";

/** Where to begin: the evidence-to-decision loop. */
const GET_STARTED: { href: string; icon: IconName; title: string; text: string }[] = [
  { href: "/assistant", icon: "assistant", title: "Ask a research question",
    text: "Research evidence, district data and a policy simulation in one cited answer." },
  { href: "/atlas", icon: "map", title: "See where the problems are",
    text: "Land use, climate risk and conflict hotspots for every district." },
  { href: "/policy-lab", icon: "flask", title: "Test a reform before rollout",
    text: "Monte Carlo scenarios with graded assumptions and a verifiable brief." },
  { href: "/innovation", icon: "bulb", title: "Fund the evidence gaps",
    text: "From Gap Radar to research call, pilot and reported outcome." },
  { href: "/data", icon: "database", title: "Check the sources",
    text: "Every dataset with its source, licence and hash; open APIs." },
];

function AskBox() {
  const [question, setQuestion] = useState("");
  const router = useRouter();
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (question.trim()) router.push(`/assistant?q=${encodeURIComponent(question)}`); }}
      className="mt-6 flex max-w-2xl gap-2">
      <div className="relative min-w-0 flex-1">
        <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Ask a policy question"
          placeholder="Ask a policy question, e.g. does digitising land records reduce disputes?"
          className="w-full rounded-[4px] border border-line bg-field py-2.5 pl-9 pr-3 text-[15px] focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20" />
      </div>
      <button className="rounded-[4px] bg-accent-solid px-5 font-medium text-white hover:brightness-110">Ask</button>
    </form>
  );
}

function StatTiles({ health }: { health: any }) {
  const tiles: [string, number | undefined][] = [
    ["Districts mapped", health?.districts],
    ["Indicator observations", health?.indicator_observations],
    ["Evidence items indexed", health?.evidence_items],
    ["Documented land conflicts", health?.land_conflicts],
    ["Dataset files catalogued", health?.datasets_catalogued],
  ];
  return (
    <dl className="grid grid-cols-2 divide-line overflow-hidden rounded-[4px] border border-line bg-panel sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
      {tiles.map(([label, value]) => (
        <div key={label} className="border-b border-line px-4 py-3 lg:border-b-0">
          <dt className="text-xs text-muted">{label}</dt>
          <dd className="mt-0.5 font-mono text-xl font-semibold tabular-nums text-accent">{value === undefined ? "…" : value.toLocaleString("en-IN")}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function OverviewPage() {
  const { data } = useApi("/api/v1/dashboards/overview");
  const { data: health } = useApi("/api/v1/health");
  const { data: gaps } = useApi("/api/v1/gaps/states");

  return (
    <div>
      <Head><title>Overview · Land Policy Intelligence Platform</title></Head>
      <section className="page-band border-b border-line">
        <div className="mx-auto w-full max-w-7xl px-4 pb-8 pt-9 md:px-8">
          <div className="eyebrow">Research and policy intelligence for land governance</div>
          <h1 className="mt-2 text-[32px] font-bold leading-tight md:text-[40px]">Land Policy Intelligence</h1>
          <p className="mt-3 max-w-2xl text-[16px] leading-relaxed text-muted">
            What is happening on India&apos;s land, what the research found, and what a reform could do before it is rolled out,
            with the source behind every number.
          </p>
          <AskBox />
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <Link href="/assistant">Open the research assistant →</Link>
            <Link href="/dashboards">View dashboards →</Link>
            <Link href="/data">Sources and licences →</Link>
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-7xl space-y-8 px-4 py-8 md:px-8">
        <StatTiles health={health} />

        <section>
          <h2 className="mb-3 text-lg font-bold">Get started</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {GET_STARTED.map((g) => (
              <Link key={g.href} href={g.href}
                className="group flex flex-col rounded-[4px] border border-line bg-panel p-4 text-ink no-underline transition hover:border-accent/50 hover:shadow-sm">
                <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-[4px] bg-accent-soft text-accent">
                  <Icon name={g.icon} className="h-[18px] w-[18px]" />
                </span>
                <span className="font-serif text-[15px] font-bold leading-snug">{g.title}</span>
                <span className="mt-1 flex-1 text-[13px] leading-relaxed text-muted">{g.text}</span>
                <span className="mt-3 text-xs font-medium text-accent group-hover:underline">Open →</span>
              </Link>
            ))}
          </div>
        </section>

        <Card title="Land cover of India">
          <LandCoverStrip />
        </Card>

        {!data ? <Spinner /> : (
          <>
            <section>
              <h2 className="mb-3 text-lg font-bold">Headline figures</h2>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[...data.policy, ...data.research.slice(0, 1)].map((k: any) => (
                  <KpiCard key={k.name} label={k.name} value={formatNumber(k.value, 2)} unit={k.unit} note={`${k.source}: ${k.definition}`} dataLabel={k.label} />
                ))}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                {data.disputes.map((k: any) => (
                  <KpiCard key={k.name} label={k.name} value={formatNumber(k.value)} unit={k.unit} note={`${k.source}: ${k.definition}`} dataLabel="OBSERVED" />
                ))}
              </div>
            </section>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Digitised is not integrated" right={<Link href="/dashboards?tab=policy-performance" className="text-sm">Policy performance →</Link>}>
                <p className="text-sm text-muted">
                  Records of Rights are almost fully computerised, but unique parcel IDs (ULPIN) range from 0% to 100% by state.
                  Dashboards show progress; this platform tests whether that progress changes outcomes.
                </p>
              </Card>
              <Card title="Research Gap Radar: high need, thin evidence" right={<Link href="/innovation" className="text-sm">Launch a call →</Link>}>
                {!gaps ? <Spinner /> : (
                  <DataTable rows={gaps.slice(0, 6)} columns={[
                    { key: "state", label: "State", render: (r) => toTitleCase(r.state) },
                    { key: "conflicts_per_10m", label: "Conflicts /10M", align: "right" },
                    { key: "ulpin_pct", label: "ULPIN %", align: "right", render: (r) => formatNumber(r.ulpin_pct) },
                    { key: "evidence_items", label: "Studies", align: "right" },
                    { key: "gap_score", label: "Gap", align: "right" },
                  ]} />
                )}
              </Card>
              <Card title="Urbanising fast while cropland shrinks" right={<Link href="/atlas?metric=built_growth_2000_2020" className="text-sm">Open atlas →</Link>}>
                <DataTable rows={data.geospatial} columns={[
                  { key: "name", label: "District", render: (r) => <DistrictLink lgd={r.district_lgd} name={r.name} /> },
                  { key: "state_name", label: "State", render: (r) => toTitleCase(r.state_name) },
                  { key: "built_growth_pct", label: "Built-up growth %", align: "right" },
                  { key: "cropland_change_pp", label: "Cropland Δ pp", align: "right" },
                ]} />
                <p className="mt-2 flex items-center gap-2 text-xs text-muted"><DataLabel label="ESTIMATED" /> GHSL 2000-2020 and Dynamic World 2017-2025</p>
              </Card>
              <Card title="Try it">
                <ul className="space-y-2 text-sm">
                  <li><Link href="/assistant?q=Does%20digitisation%20of%20land%20records%20reduce%20land%20disputes%3F">Ask the assistant a cited question</Link></li>
                  <li><Link href={`/assistant?q=${encodeURIComponent("What does existing research say about land conflict, which districts currently show the highest risk, and what could happen if conflict-resolution capacity is increased?")}`}>
                    Research, data and a Policy Digital Twin simulation in one question</Link></li>
                  <li><Link href="/atlas">Map land-use change, climate exposure and conflict hotspots</Link></li>
                  <li><Link href="/policy-lab">Simulate a zoning rule or land-acquisition reform</Link></li>
                  <li><Link href="/dashboards">See all seven dashboards</Link></li>
                </ul>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
