// HTTP client for the FastAPI backend (proxied at /api by next.config.ts).

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

type Params = Record<string, unknown>;

function toQueryString(params?: Params): string {
  if (!params) return "";
  const pairs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .flatMap(([k, v]) => (Array.isArray(v) ? v.map((x) => [k, x]) : [[k, v]]))
    .map(([k, v]) => `${encodeURIComponent(String(k))}=${encodeURIComponent(String(v))}`);
  return pairs.length ? `?${pairs.join("&")}` : "";
}

async function request<T>(method: string, path: string, body?: unknown, raw = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const json = await res.json();
      message = typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail ?? json);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  return (raw ? res : res.json()) as Promise<T>;
}

export const api = {
  get: <T = any>(path: string, params?: Params) => request<T>("GET", path + toQueryString(params)),
  post: <T = any>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T = any>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  del: <T = any>(path: string) => request<T>("DELETE", path),
  /** Raw Response, for file downloads. */
  raw: (path: string) => request<Response>("GET", path, undefined, true),
};

/** Save a Response body as a file in the browser. */
export async function downloadResponse(res: Response, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await res.blob());
  a.download = filename;
  a.click();
}
