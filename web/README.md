# Web app (Next.js, Pages Router)

Each page is one named file in `pages/`; the file name is the URL.

```
pages/
  index.tsx            /                 overview
  search.tsx           /search           search & browse the repository
  assistant.tsx        /assistant        cited research assistant
  atlas.tsx            /atlas            GIS atlas
  dashboards.tsx       /dashboards       7 dashboards (?tab=research, policy-performance, land-use, ...)
  analytics.tsx        /analytics        trends, policy evaluation, emerging trends, model registry
  policy-lab.tsx       /policy-lab       scenario simulation and policy briefs
  workspaces.tsx       /workspaces       collaborative workspaces
  innovation.tsx       /innovation       gap radar, calls, pilots, contributions
  data.tsx             /data             dataset catalogue, APIs, land records
  admin.tsx            /admin            audit log, users, API keys
  login.tsx            /login
  evidence/[id].tsx    /evidence/:id     (folders only where the URL has an id)
  districts/[id].tsx   /districts/:id
  workspaces/[id].tsx  /workspaces/:id
  calls/[id].tsx       /calls/:id
  _app.tsx, _document.tsx                app shell, global CSS, auth provider
```

Tabs inside a page live in the URL (`?tab=`) and each tab's code is its own file in `components/<page>/`.

```
components/ui/          Card, Button, DataTable, KpiCard, ... (import from "@/components/ui")
components/layout/      AppShell (sidebar), PageContainer, TabbedPage
components/charts/      EChart wrapper and chart option builders
components/map/         DistrictMap (MapLibre) and colour scales
components/<page>/      the pieces of one page (dashboards, analytics, atlas, policy-lab, ...)
config/                 navigation, geography and innovation constants
hooks/                  useApi (GET with state), useTabQuery (?tab= state)
lib/                    API client, auth provider, number formatting, EN/HI strings
styles/globals.css      colour tokens and Tailwind
e2e/walkthrough.mjs     browser walkthrough: node e2e/walkthrough.mjs <screenshot-dir>
```

Build and run: `npm install`, `npx next build`, then `..\start.ps1` from the project root (starts the API on :8000 and this app on :3000).
