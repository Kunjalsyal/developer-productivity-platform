import { useState } from "react";
import { api, errMsg } from "../api";
import { Box, Btn, Gate, HitCard, Input, PageTitle } from "../components/ui";
import type { Hit } from "../types";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [ms, setMs] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <PageTitle title="Code search" sub="Search by intent, not exact words. Try “where is rate limiting enforced” or “how are redirects handled”." />
      <Gate>
        {(repo) => {
          async function run() {
            if (q.trim().length < 2) return;
            setBusy(true); setErr(null);
            try {
              const r = await api<{ results: Hit[]; latency_ms: number }>(`/api/repositories/${repo.id}/search`, { json: { query: q, top_k: 5 } });
              setHits(r.results); setMs(r.latency_ms);
            } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
          }
          return (
            <>
              <div className="mb-4 flex gap-2">
                <Input aria-label="Search query" value={q} placeholder="Describe what you are looking for" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void run()} />
                <Btn onClick={run} disabled={busy}>{busy ? "…" : "Search"}</Btn>
              </div>
              {err && <Box><span className="text-warn">{err}</span></Box>}
              {hits && <p className="mb-2 text-sm text-mute">{hits.length} results · {ms} ms</p>}
              {hits?.map((h) => <HitCard key={h.chunk_id} h={h} />)}
            </>
          );
        }}
      </Gate>
    </>
  );
}
