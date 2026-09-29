# Land Policy Intelligence Platform (SIH26019)

A national platform for land-governance research and policy innovation for the Department of Land Resources:
find evidence, see where problems are, test a reform before rollout, and commission research where evidence is thin.

## What it does (the 12 deliverables of SIH26019)

| # | Deliverable | Where |
|---|---|---|
| 7 | Centralised repository: 15,000 research papers, policy reports, legal and government documents, datasets, 1,250 case studies, with provenance | **Search & Repository**, **Data & APIs** |
| 8 | AI search and recommendations: keyword + semantic (hybrid), filters, "recommended because…" | **Search**, evidence pages, workspaces |
| 9 | Collaborative workspaces: policy question, members and roles, evidence, versioned notes, review and approval, comments, tasks, BibTeX/RIS | **Workspaces** |
| 10 | GIS: land use, climate vulnerability, infrastructure and policy impact for 731 districts (Survey of India boundaries), conflict and landslide points, cadastral parcels, spatial questions | **GIS Atlas**, district profiles |
| 11 | Analytics and decision support: trends, difference-in-differences evaluation, emerging trends, anomalies, correlation, model registry | **Analytics** |
| 12 | Policy simulation: zoning, land-acquisition rules and revenue-court levers; Monte Carlo ranges, tornado chart, graded assumptions, comparison, verifiable brief | **Policy Lab** |
| 13 | Integration of satellite and remote sensing (Earth Engine), land records (DILRMP-MIS, cadastral maps), socio-economic (SHRUG, NFHS-5) and geospatial data | `pipelines/`, `etl/` |
| 14 | AI research tools: cited literature synthesis with a verifier and refusal, evidence matrix, conflict flags, topic trends, forecasts with back-tests, scenarios | **Research Assistant**, **Analytics** |
| 15 | Innovation portal: Gap Radar → calls (DoLR grant schemes, hackathons, pilots, competitions) → applications, referee scoring, award and instalments → pilots → outcomes | **Innovation Portal** |
| 16 | Dashboards: research outputs, policy performance, land-use trends, climate resilience, land disputes, project outcomes, geospatial insights | **Dashboards** |
| 17 | Secure role-based access: 6 roles, restricted datasets, access requests, anonymisation (k-anonymity, pseudonyms), tamper-evident audit log | **Data & APIs → Land records**, **Administration** |
| 18 | APIs: REST (OpenAPI), OGC API – Features, OAI-PMH, DCAT, partner API keys, connector contracts | **Data & APIs → APIs** |

Every number carries a label: OBSERVED, ESTIMATED (satellite-derived), SIMULATED, PREDICTED or CORRELATIONAL.
Parcel-level land records are **synthetic** (real Dhamtari parcel boundaries, generated owners); no real personal data is held.

## Layout

```
pipelines/   data acquisition: fetch.py (public sources), gee_district_indicators.py (Earth Engine)
data/        downloaded raw data + hash-chained manifest (git-ignored)
etl/         build_db.py (DuckDB analytics DB), build_ai.py (semantic index), build_synthetic.py, seed_app.py
backend/     FastAPI app: core/ (db, security), routers/ (one per module), services/ (search, synthesis, sim, anonymise)
web/         Next.js 16 app (MapLibre maps, ECharts)
db/          derived databases, semantic index, demo accounts (git-ignored)
tests/       smoke_test.py (API, 88 checks);  web/e2e/walkthrough.mjs (UI, 30 checks)
```

## Set up once

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r pipelines\requirements.txt -r backend\requirements.txt

python pipelines\fetch.py --out data          # public data (~2.5 GB); add --tier full for ~6 GB more
# optional: Earth Engine satellite panel -> data\temporal (see pipelines\gee_district_indicators.py)
python etl\build_synthetic.py                 # synthetic land records on real cadastral parcels
python etl\build_db.py                        # analytics database  -> db\lpip.duckdb
python etl\build_ai.py                        # semantic search index -> db\ai
python etl\seed_app.py                        # demo accounts (db\demo_accounts.txt) and example portal content

cd web; npm install; cd ..
```

## Run (development: two terminals, auto-reload)

Open two terminals in the project folder. Changes to the code are picked up automatically; there is nothing to
rebuild or restart. Stop either server with **Ctrl+C** in its terminal.

**Terminal 1: backend API** (http://127.0.0.1:8000, reloads when a file under `backend/` changes)

```powershell
.venv\Scripts\python -m backend
```

**Terminal 2: frontend** (http://localhost:3000, hot reload)

```powershell
cd web
npm run dev
```

Open http://localhost:3000. API documentation: http://localhost:3000/docs. Sign in with an account from `db\demo_accounts.txt`
(one per role: admin, official, reviewer, institution admin, researcher).

**Production-style run** (optimised build, e.g. for a demo): `cd web; npm run build; npm run start` with the backend as above.
`start.ps1` / `stop.ps1` do the same in the background; `stop.ps1` also stops anything left running on ports 8000 and 3000.

## Test

```powershell
python tests\smoke_test.py            # 88 API checks, in-process
cd web; node e2e\walkthrough.mjs out  # 30 UI checks in Edge (needs both servers running)
```

## Research assistant (Policy Digital Twin)

`POST /api/v1/assistant/ask` (UI: **Research Assistant**) never goes Question -> LLM -> Answer. It runs:

```
Question -> Query Router (documents? data? policy?)       services/query_router.py
         -> RAG (hybrid retrieval, cited sentences)        services/synthesis.py
          + SQL / Analytics (rankings, trends, correlation) services/data_query.py
          + Policy Digital Twin (current state + lever ->   services/digital_twin.py (uses services/sim.py)
            Monte Carlo P10/P50/P90, stress test, sensitivity)
         -> Evidence verification -> Evidence matrix -> Conflict + uncertainty -> Evidence gaps
         -> Synthesis -> cited answer + traceability        services/research_assistant.py
         -> Evidence gap -> draft research call -> pilot -> new evidence (Innovation Portal)
```

Every claim in the answer is a row of the evidence matrix (document / analytics / simulation / assumption / conflict)
with its evidence and status; simulated results are labelled SIMULATED and phrased as conditional on their assumptions.

## AI and data sovereignty

Everything runs **fully offline** with no API keys: BM25 + latent semantic index for retrieval, extractive cited
sentences, rule-based routing, Monte Carlo simulation, and template synthesis from the verified evidence matrix.
Optional LLM wording (`backend/app/services/llm.py`) is **off** by default; when enabled it may only rephrase verified
claims, and any sentence that cites no claim or states a number not in the matrix is dropped:

```
LPIP_LLM=ollama      local open-weight model, no key (install Ollama, then: ollama pull qwen2.5:3b)
LPIP_LLM=anthropic   Claude (needs Anthropic credentials)
```

## Data sources and licences

See **Data & APIs → Dataset catalogue** in the app, or `data/catalog.csv`. Main sources: DILRMP-MIS, Survey of India and
LGD (via open mirrors), SHRUG (CC BY-NC-SA), NFHS-5, NDEM/GSI/NGDR hazards, GHSL, Earth Engine (Dynamic World, MODIS,
GHSL, VIIRS, CHIRPS), OpenAlex, World Bank Documents, DoLR, DST, Land Conflict Watch, OpenStreetMap (ODbL).
