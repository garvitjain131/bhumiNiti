// UI walkthrough of every screen with real clicks, as the public, a researcher, an official and an admin.
// Run with both servers up:  node e2e/walkthrough.mjs <screenshot-dir>
// Uses the Edge already installed on Windows (playwright-core; no browser download). Demo credentials are read
// from db/demo_accounts.txt (created by etl/seed_app.py).
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const OUT = process.argv[2] ?? "e2e-shots";
const BASE = process.env.BASE ?? "http://localhost:3000";
const EDGE = process.env.EDGE ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
fs.mkdirSync(OUT, { recursive: true });

const creds = {};
for (const line of fs.readFileSync(path.resolve("../db/demo_accounts.txt"), "utf8").split(/\r?\n/)) {
  const p = line.trim().split(/\s+/);
  if (p.length === 3 && p[1].includes("@") && !creds[p[0]]) creds[p[0]] = { email: p[1], pw: p[2] };
}

const results = [];
const errors = [];
const check = (name, ok, detail = "") => { results.push([name, ok]); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  - " + detail : ""}`); };

const browser = await chromium.launch({ executablePath: EDGE, headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });

async function session(role) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(`${role}: ${e.message.slice(0, 200)}`));
  page.on("console", (m) => { if (m.type() === "error" && !/401|403|Failed to load resource/.test(m.text())) errors.push(`${role} console: ${m.text().slice(0, 200)}`); });
  if (role !== "public") {
    await page.goto(`${BASE}/login`);
    await page.fill('input[type="email"]', creds[role].email);
    await page.fill('input[type="password"]', creds[role].pw);
    await page.click('button:has-text("Sign in")');
    await page.waitForURL(`${BASE}/`);
  }
  return page;
}
const shot = (page, n) => page.screenshot({ path: path.join(OUT, `${n}.png`), fullPage: false });
const text = (page) => page.locator("main").innerText();

// ---------------- public
{
  const p = await session("public");
  await p.goto(BASE, { waitUntil: "networkidle" });
  check("overview KPIs", /RECORDS OF RIGHTS COMPUTERISED/i.test(await text(p)));
  await shot(p, "01-overview");

  await p.goto(`${BASE}/search?q=land%20pooling%20farmers`, { waitUntil: "networkidle" });
  await p.waitForSelector("article");
  check("search results", (await p.locator("article").count()) > 5);
  await shot(p, "02-search");
  await p.locator("article a").first().click();
  await p.waitForSelector("text=Related evidence");
  await p.waitForSelector("text=Recommended because", { timeout: 15000 });
  check("evidence detail + recommendations", true);
  await shot(p, "03-evidence");

  await p.goto(`${BASE}/assistant?q=${encodeURIComponent("Does digitisation of land records reduce land disputes?")}`, { waitUntil: "networkidle" });
  await p.waitForSelector("text=Evidence matrix", { timeout: 20000 });
  check("assistant cited answer", (await p.locator('a[href^="#claim-D"]').count()) > 0);
  await shot(p, "04-assistant");
  await p.goto(`${BASE}/assistant?q=${encodeURIComponent("What does existing research say about land conflict, which districts currently show the highest risk, and what could happen if conflict-resolution capacity is increased?")}`, { waitUntil: "networkidle" });
  await p.waitForSelector("text=Baseline vs policy scenario", { timeout: 30000 });
  check("assistant multi-domain: RAG + analytics + digital twin",
    (await p.locator('a[href^="#claim-D"]').count()) > 0 && (await p.locator('a[href^="#claim-A"]').count()) > 0 && (await p.locator('a[href^="#claim-S"]').count()) > 0);
  await shot(p, "04b-assistant-digital-twin");
  await p.getByRole("link", { name: "open this scenario in the Policy Lab" }).click();
  await p.waitForSelector("text=Opened stored scenario run", { timeout: 20000 });
  check("assistant scenario opens in Policy Lab", (await p.getByRole("button", { name: "8. Export policy brief" }).count()) === 1);

  await p.goto(`${BASE}/atlas`, { waitUntil: "networkidle" });
  await p.waitForTimeout(4000);
  const canvas = p.locator(".maplibregl-canvas");
  const box = await canvas.boundingBox();
  await p.mouse.click(box.x + box.width * 0.45, box.y + box.height * 0.45);
  await p.waitForSelector("text=Full profile", { timeout: 15000 });
  check("atlas district click opens profile", true);
  await p.check("text=Cadastral parcels (Dhamtari)");
  await p.waitForTimeout(1500);
  for (let i = 0; i < 4; i++) { await p.locator(".maplibregl-ctrl-zoom-in").click(); await p.waitForTimeout(700); }
  await p.waitForTimeout(3000);
  await shot(p, "05-atlas-parcels");
  const cb = await canvas.boundingBox();
  await p.mouse.click(cb.x + cb.width / 2, cb.y + cb.height / 2);
  await p.waitForTimeout(2500);
  check("parcel click (public sees sign-in prompt)", /Parcel|sign in/i.test(await text(p)));
  await p.getByRole("button", { name: "Find districts" }).click();
  await p.waitForSelector("text=districts match");
  check("spatial question", true);

  for (const [tab, label] of [["research", "Research papers per year"], ["policy-performance", "DILRMP progress by state"], ["land-use", "Cropland and forest share"],
    ["climate-resilience", "Annual rainfall"], ["land-disputes", "Conflicts by sector"], ["project-outcomes", "Platform pilots"], ["geospatial", "Pressure overlap"]]) {
    await p.goto(`${BASE}/dashboards?tab=${tab}`, { waitUntil: "networkidle" });
    await p.waitForSelector(`text=${label}`, { timeout: 15000 });
    check(`dashboard ${tab}`, true);
    if (["policy-performance", "land-disputes", "land-use"].includes(tab)) await shot(p, `06-dashboard-${tab}`);
  }

  await p.goto(`${BASE}/analytics`, { waitUntil: "networkidle" });
  await p.waitForSelector("text=Back-test MAPE", { timeout: 20000 });
  check("analytics trend + forecast", true);
  await p.getByRole("tab", { name: "Policy evaluation" }).click();
  await p.getByRole("button", { name: "Run evaluation" }).click();
  await p.waitForSelector("text=DiD estimate", { timeout: 20000 });
  check("policy evaluation", true);
  await shot(p, "07-analytics-did");

  await p.goto(`${BASE}/innovation`, { waitUntil: "networkidle" });
  await p.waitForSelector("text=Highest gaps");
  check("gap radar", true);
  await shot(p, "08-gap-radar");

  await p.goto(`${BASE}/data?tab=land-records`, { waitUntil: "networkidle" });
  check("public cannot request records", /Sign in first/.test(await text(p)));
  await p.getByRole("button", { name: "Switch language" }).click();
  check("Hindi interface", /जीआईएस एटलस/.test(await p.locator('nav[aria-label="Main"]').innerText()));
  await p.locator("button:has-text('English')").click();
  await p.context().close();
}

// ---------------- official: policy lab, brief, verify, drafting a call
{
  const p = await session("official");
  await p.goto(`${BASE}/policy-lab`, { waitUntil: "networkidle" });
  await p.fill('label:has-text("State") input', "Maharashtra");
  await p.getByRole("button", { name: "5. Run scenario" }).click();
  await p.waitForSelector("text=What drives the result", { timeout: 30000 });
  check("lab zoning scenario", /avoids a median/.test(await text(p)));
  await p.getByRole("button", { name: "Keep for comparison" }).click();
  await p.getByRole("button", { name: "8. Export policy brief" }).click();
  await p.waitForSelector("textarea[aria-label=\"Brief\"]");
  await p.getByRole("button", { name: /^Verify/ }).click();
  await p.waitForSelector("text=Verified: unaltered");
  check("brief verified", true);
  await shot(p, "09-lab");
  await p.fill("textarea[aria-label=\"Brief\"]", (await p.inputValue("textarea[aria-label=\"Brief\"]")).replace("median", "mean"));
  await p.getByRole("button", { name: /^Verify/ }).click();
  await p.waitForSelector("text=Not verified");
  check("tampered brief rejected", true);

  await p.goto(`${BASE}/innovation`, { waitUntil: "networkidle" });
  await p.locator("button:has-text('Draft a call')").first().click();
  await p.waitForSelector("text=Draft call created");
  check("gap to draft call", true);

  await p.goto(`${BASE}/workspaces/1`, { waitUntil: "networkidle" });
  await p.waitForSelector("text=Evidence collection");
  check("workspace detail", true);
  await shot(p, "10-workspace");
  await p.context().close();
}

// ---------------- researcher: request access; official approves; researcher exports
{
  const r = await session("researcher");
  await r.goto(`${BASE}/data?tab=land-records`, { waitUntil: "networkidle" });
  await r.fill("textarea", "UI walkthrough: studying mutation delays and women's ownership at village level.");
  await r.getByRole("button", { name: "Request access to parcel-level records" }).click();
  await r.waitForSelector("text=pending");
  check("access request submitted", true);
  const o = await session("official");
  await o.goto(`${BASE}/data?tab=land-records`, { waitUntil: "networkidle" });
  await o.locator("button:has-text('Approve')").first().click();
  await o.waitForTimeout(1000);
  await o.context().close();
  await r.reload({ waitUntil: "networkidle" });
  await r.getByRole("button", { name: "Preview anonymised export" }).click();
  await r.waitForSelector("text=Anonymisation report");
  check("anonymised export report", /k=5/.test(await text(r)));
  await r.getByRole("button", { name: "Browse (masked)" }).click();
  await r.waitForTimeout(1500);
  check("masked names", /\*\*\*/.test(await text(r)));
  await shot(r, "11-anonymisation");
  await r.context().close();
}

// ---------------- admin: audit chain
{
  const a = await session("admin");
  await a.goto(`${BASE}/admin`, { waitUntil: "networkidle" });
  await a.waitForSelector("text=Hash chain intact");
  check("audit chain intact (admin)", true);
  await shot(a, "12-admin-audit");
  await a.context().close();
}

await browser.close();
console.log(`\n${results.filter((r) => r[1]).length}/${results.length} passed`);
if (errors.length) { console.log("Browser errors:"); errors.slice(0, 15).forEach((e) => console.log("  " + e)); }
process.exit(results.every((r) => r[1]) && !errors.length ? 0 : 1);
