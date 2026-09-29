import type { NextConfig } from "next";

// The FastAPI backend runs on :8000. Proxying keeps the browser on one origin (no CORS, cookies-free token auth).
const API = process.env.LPIP_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Old links keep working after pages were renamed.
  redirects() {
    return [
      { source: "/lab", destination: "/policy-lab", permanent: true },
      { source: "/district/:id", destination: "/districts/:id", permanent: true },
      { source: "/innovation/calls/:id", destination: "/calls/:id", permanent: true },
    ];
  },
  rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/ogc/:path*", destination: `${API}/ogc/:path*` },
      { source: "/ogc", destination: `${API}/ogc` },
      { source: "/oai", destination: `${API}/oai` },
      { source: "/tiles/:path*", destination: `${API}/tiles/:path*` },
      { source: "/docs", destination: `${API}/docs` },
      { source: "/openapi.json", destination: `${API}/openapi.json` },
    ];
  },
};

export default nextConfig;
