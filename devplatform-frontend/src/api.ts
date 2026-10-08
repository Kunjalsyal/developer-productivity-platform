const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const KEY = import.meta.env.VITE_API_KEY as string | undefined;

/** Optional GitHub token for private repos; kept for the tab session only, sent as a header, never stored by the backend. */
export const ghToken = {
  get: () => sessionStorage.getItem("gh_token") ?? "",
  set: (v: string) => (v ? sessionStorage.setItem("gh_token", v) : sessionStorage.removeItem("gh_token")),
};

export async function api<T>(path: string, init: { method?: string; json?: unknown; github?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  if (KEY) headers["X-API-Key"] = KEY;
  if (init.github && ghToken.get()) headers["X-GitHub-Token"] = ghToken.get();
  const res = await fetch(`${BASE}${path}`, {
    method: init.method ?? (init.json !== undefined ? "POST" : "GET"),
    headers,
    body: init.json !== undefined ? JSON.stringify(init.json) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* keep default */ }
    throw new Error(detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));
