import { useEffect, useState } from "react";
import { api, errMsg } from "../api";
import { Box, Btn, Gate, PageTitle } from "../components/ui";
import type { PRItem, PRSummary } from "../types";

function Pulls({ repoId }: { repoId: string }) {
  const [items, setItems] = useState<PRItem[] | null>(null);
  const [sums, setSums] = useState<Record<number, PRSummary>>({});
  const [loading, setLoading] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<PRItem[]>(`/api/repositories/${repoId}/pulls`, { github: true }).then(setItems).catch((e) => setErr(errMsg(e)));
  }, [repoId]);

  async function summarize(n: number) {
    setLoading(n); setErr(null);
    try {
      const s = await api<PRSummary>(`/api/repositories/${repoId}/pulls/${n}/summary`, { method: "POST", github: true });
      setSums((m) => ({ ...m, [n]: s }));
    } catch (e) { setErr(errMsg(e)); } finally { setLoading(null); }
  }

  return (
    <>
      {err && <Box><span className="text-warn">{err}</span></Box>}
      {items && !items.length && <p className="text-mute">No open pull requests.</p>}
      {items?.map((p) => {
        const s = sums[p.number];
        return (
          <Box key={p.number}>
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <a className="font-semibold hover:underline" href={p.url} target="_blank" rel="noreferrer">#{p.number} {p.title}</a>
                <div className="text-sm text-mute">{p.author} · updated {new Date(p.updated_at).toLocaleDateString()}</div>
              </div>
              <Btn ghost disabled={loading === p.number} onClick={() => summarize(p.number)}>{loading === p.number ? "Summarizing…" : s ? "Refresh" : "Summarize"}</Btn>
            </div>
            {s && (
              <div className="mt-3 border-t border-line pt-3 text-sm">
                <p>{s.summary}</p>
                <p className="mt-2"><b>Why:</b> {s.why}</p>
                {s.review_notes.length > 0 && <><b className="mt-2 block">Reviewer notes</b><ul className="ml-5 list-disc">{s.review_notes.map((n, i) => <li key={i}>{n}</li>)}</ul></>}
                <b className="mt-2 block">Changed files</b>
                <div className="flex flex-wrap gap-1">{s.related.changed_files.map((f) => <span key={f} className="rounded bg-cite px-2 py-0.5 font-mono text-xs text-cite-ink">{f}</span>)}</div>
                {s.related.discussion.length > 0 && <><b className="mt-2 block">Related discussion</b><ul className="ml-5 list-disc">{s.related.discussion.map((d, i) => <li key={i}>{d.url ? <a className="text-accent underline" href={d.url} target="_blank" rel="noreferrer">{d.kind} {d.ref}</a> : `${d.kind} ${d.ref}`}: <span className="text-mute">{d.excerpt.slice(0, 120)}</span></li>)}</ul></>}
                {s.related.docs.length > 0 && <><b className="mt-2 block">Related docs</b><ul className="ml-5 list-disc">{s.related.docs.map((d, i) => <li key={i}>{d.title} <span className="text-mute">({d.path})</span></li>)}</ul></>}
              </div>
            )}
          </Box>
        );
      })}
    </>
  );
}

export default function PullsPage() {
  return (
    <>
      <PageTitle title="Pull requests" sub="Open PRs turned into plain-language summaries, linked to the discussion, docs and files they touch." />
      <Gate>{(repo) => <Pulls key={repo.id} repoId={repo.id} />}</Gate>
    </>
  );
}
