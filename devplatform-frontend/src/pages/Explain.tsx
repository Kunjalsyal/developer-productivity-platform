import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { api, errMsg } from "../api";
import { Box, Btn, CiteChip, Gate, HitCard, Input, PageTitle } from "../components/ui";
import type { Citation, Explain } from "../types";

const REASONS: Record<string, string> = {
  retrieval_below_threshold: "Nothing in the indexed code was similar enough to this question.",
  model_reported_insufficient_context: "The code that was found does not contain enough to answer.",
  no_valid_citations: "The model's answer did not point at any real piece of code.",
  ungrounded_identifiers: "The answer mentioned names that do not appear in the retrieved code.",
  unparseable_llm_output: "The model returned something that could not be checked.",
};

function Answer({ text, cites }: { text: string; cites: Citation[] }) {
  return (
    <p className="leading-relaxed">
      {text.split(/(\[\d+\])/g).map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (!m) return <span key={i}>{part}</span>;
        const c = cites.find((x) => x.index === Number(m[1]));
        return (
          <a key={i} href={`#cite-${m[1]}`} title={c ? `${c.file_path}:${c.start_line}-${c.end_line}` : ""}
             className="mx-0.5 rounded bg-cite px-1.5 font-mono text-xs text-cite-ink no-underline">{m[1]}</a>
        );
      })}
    </p>
  );
}

export default function ExplainPage() {
  const [q, setQ] = useState("");
  const [log, setLog] = useState<{ q: string; res?: Explain; err?: string }[]>([]);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <PageTitle title="Explainer" sub="Every answer cites the file and lines it comes from. When the indexed code doesn't support an answer, it says so instead of guessing." />
      <Gate>
        {(repo) => {
          async function ask() {
            const question = q.trim();
            if (question.length < 2) return;
            setQ(""); setBusy(true);
            try {
              const res = await api<Explain>(`/api/repositories/${repo.id}/explain`, { json: { query: question } });
              setLog((l) => [...l, { q: question, res }]);
            } catch (e) { setLog((l) => [...l, { q: question, err: errMsg(e) }]); } finally { setBusy(false); }
          }
          return (
            <>
              {log.map((m, i) => (
                <div key={i} className="mb-6">
                  <p className="mb-2 font-semibold">{m.q}</p>
                  {m.err && <Box><span className="text-warn">{m.err}</span></Box>}
                  {m.res && (
                    <>
                      <Box className={`border-l-4 ${m.res.low_confidence ? "border-l-warn" : "border-l-ok"}`}>
                        {m.res.low_confidence ? (
                          <>
                            <b className="flex items-center gap-2 text-warn"><AlertTriangle size={16} /> Low confidence — no answer given</b>
                            <p className="mt-1">{REASONS[m.res.reason ?? ""] ?? m.res.reason}</p>
                            <p className="mt-1 text-sm text-mute">Closest matches are shown below. Try rephrasing or index more of the repository.</p>
                          </>
                        ) : (
                          <>
                            <Answer text={m.res.answer} cites={m.res.citations} />
                            <p className="mt-2 text-xs text-mute">
                              confidence {m.res.confidence.toFixed(2)} · {m.res.latency_ms} ms
                              {m.res.unverified_terms.length > 0 && ` · unverified names: ${m.res.unverified_terms.join(", ")}`}
                            </p>
                          </>
                        )}
                      </Box>
                      {m.res.citations.map((c) => (
                        <div key={c.chunk_id} id={`cite-${c.index}`}>
                          <HitCard h={c} badge={<span className="mr-2 rounded bg-cite px-1.5 font-mono text-xs text-cite-ink">[{c.index}]</span>} />
                        </div>
                      ))}
                      {m.res.related.length > 0 && (
                        <>
                          <p className="mb-1 text-xs uppercase tracking-wide text-mute">{m.res.low_confidence ? "Closest matches" : "Also related"}</p>
                          {m.res.related.map((c) => <div key={c.chunk_id} className="flex items-center gap-2 py-0.5 text-sm"><CiteChip h={c} /> <span className="font-mono">{c.name}</span></div>)}
                        </>
                      )}
                    </>
                  )}
                </div>
              ))}
              <div className="flex gap-2">
                <Input aria-label="Question" value={q} placeholder="Ask about the codebase, e.g. how are failed requests retried?" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void ask()} />
                <Btn onClick={ask} disabled={busy}>{busy ? "Thinking…" : "Ask"}</Btn>
              </div>
            </>
          );
        }}
      </Gate>
    </>
  );
}
