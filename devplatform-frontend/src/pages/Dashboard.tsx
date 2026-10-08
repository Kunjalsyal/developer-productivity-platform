import { RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, errMsg, ghToken } from "../api";
import { Box, Btn, Input, PageTitle } from "../components/ui";
import { useRepos } from "../state/RepoContext";
import type { Repo } from "../types";

const badge: Record<Repo["index_status"], string> = {
  pending: "text-mute", indexing: "text-warn", ready: "text-ok", failed: "text-warn",
};

export default function Dashboard() {
  const { repos, error, refresh, select, selected } = useRepos();
  const [url, setUrl] = useState("https://github.com/psf/requests");
  const [token, setToken] = useState(ghToken.get());
  const [notion, setNotion] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function connect() {
    setBusy(true); setMsg(null);
    try {
      ghToken.set(token.trim());
      const r = await api<Repo>("/api/repositories", { json: { url, include_notion: notion }, github: true });
      select(r.id);
      await refresh();
    } catch (e) { setMsg(errMsg(e)); } finally { setBusy(false); }
  }

  async function act(fn: () => Promise<unknown>) {
    try { await fn(); await refresh(); } catch (e) { setMsg(errMsg(e)); }
  }

  return (
    <>
      <PageTitle title="Dashboard" sub="Connect a GitHub repository. The backend downloads it, splits it into function-level chunks, embeds them and stores them in pgvector." />
      {error && <Box><b className="text-warn">Backend unreachable:</b> {error}</Box>}
      <Box>
        <label className="text-sm font-semibold" htmlFor="url">GitHub repository URL</label>
        <div className="mb-3 mt-1"><Input id="url" value={url} onChange={(e) => setUrl(e.target.value)} /></div>
        <label className="text-sm font-semibold" htmlFor="tok">GitHub token <span className="font-normal text-mute">(optional, for private repos)</span></label>
        <div className="mb-3 mt-1"><Input id="tok" type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="github_pat_…" /></div>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={notion} onChange={(e) => setNotion(e.target.checked)} /> Also index my Notion workspace (needs NOTION_TOKEN on the backend)
        </label>
        <Btn onClick={connect} disabled={busy || !url.trim()}>{busy ? "Connecting…" : "Connect and index"}</Btn>
        {msg && <p className="mt-3 text-sm text-warn">{msg}</p>}
      </Box>

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-mute">Repositories</h2>
      {!repos.length && <p className="text-mute">Nothing connected yet.</p>}
      {repos.map((r) => (
        <Box key={r.id} className={selected?.id === r.id ? "border-accent" : ""}>
          <div className="flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1">
              <b>{r.owner}/{r.name}</b>
              <span className={`ml-3 text-sm font-medium ${badge[r.index_status]}`}>{r.index_status}</span>
              <div className="text-sm text-mute">
                {r.index_status === "ready" ? `${r.file_count} files · ${r.chunk_count} chunks · ${r.commit_sha?.slice(0, 7) ?? ""}` : r.index_error ?? "Indexing in the background…"}
              </div>
            </div>
            {r.index_status === "ready" && selected?.id !== r.id && <Btn ghost onClick={() => select(r.id)}>Use</Btn>}
            <Btn ghost aria-label="Re-index" onClick={() => act(() => api(`/api/repositories/${r.id}/reindex`, { method: "POST", github: true }))}><RefreshCw size={14} /></Btn>
            <Btn ghost aria-label="Delete" onClick={() => confirm(`Delete ${r.name}?`) && act(() => api(`/api/repositories/${r.id}`, { method: "DELETE" }))}><Trash2 size={14} /></Btn>
          </div>
        </Box>
      ))}
    </>
  );
}
