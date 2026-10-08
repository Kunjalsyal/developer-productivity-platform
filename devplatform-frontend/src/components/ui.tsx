import { Link } from "react-router-dom";
import { useRepos } from "../state/RepoContext";
import type { Citation, Hit, Repo } from "../types";
import type { ReactNode } from "react";

export const Box = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`mb-3 rounded-lg border border-line bg-panel p-4 ${className}`}>{children}</div>
);

export const Btn = ({ children, ghost, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { ghost?: boolean }) => (
  <button
    {...p}
    className={`rounded-md px-4 py-2 text-sm font-semibold disabled:opacity-50 ${
      ghost ? "bg-code text-ink" : "bg-accent text-accent-ink"
    } ${p.className ?? ""}`}
  >
    {children}
  </button>
);

export const Input = (p: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input {...p} className={`w-full rounded-md border border-line bg-bg px-3 py-2 text-sm ${p.className ?? ""}`} />
);

export const PageTitle = ({ title, sub }: { title: string; sub: string }) => (
  <>
    <h1 className="mb-1 text-2xl font-semibold">{title}</h1>
    <p className="mb-5 max-w-[62ch] text-mute">{sub}</p>
  </>
);

export const CiteChip = ({ h }: { h: Pick<Hit, "file_path" | "start_line" | "end_line" | "source" | "url"> }) => {
  const label = h.source === "notion" ? h.file_path.replace("notion:", "Notion · ") : `${h.file_path}:${h.start_line}-${h.end_line}`;
  const cls = "inline-block rounded bg-cite px-2 py-0.5 font-mono text-xs text-cite-ink";
  return h.url ? <a className={cls} href={h.url} target="_blank" rel="noreferrer">{label}</a> : <span className={cls}>{label}</span>;
};

export const CodeBlock = ({ h }: { h: Hit }) => (
  <pre className="mt-2 overflow-x-auto rounded-md bg-code py-2 font-mono text-[12.5px] leading-relaxed">
    {h.content.split("\n").map((l, i) => (
      <div key={i} className="whitespace-pre px-3">
        <span className="mr-3 inline-block w-[4ch] select-none text-right text-mute">{h.start_line + i}</span>
        {l}
      </div>
    ))}
  </pre>
);

export const HitCard = ({ h, badge }: { h: Hit | Citation; badge?: ReactNode }) => (
  <Box>
    <span className="float-right text-xs text-mute">{h.similarity.toFixed(2)} similarity</span>
    {badge}
    <b className="font-mono text-sm">{h.name}</b>
    <span className="ml-2 rounded border border-line px-1.5 text-xs text-mute">{h.language ?? h.source}</span>
    <div className="mt-1"><CiteChip h={h} /></div>
    {h.source !== "notion" && h.source !== "doc" ? <CodeBlock h={h} /> : (
      <p className="mt-2 whitespace-pre-wrap text-sm text-mute">{h.content.slice(0, 600)}</p>
    )}
  </Box>
);

export function Gate({ children }: { children: (repo: Repo) => ReactNode }) {
  const { selected, error } = useRepos();
  if (error) return <Box><b className="text-warn">Can't reach the backend.</b> <span className="text-mute">{error}</span></Box>;
  if (!selected || selected.index_status !== "ready")
    return (
      <Box>
        No indexed repository yet. <Link className="text-accent underline" to="/">Connect one on the Dashboard</Link> and wait for it to say <b>ready</b>.
      </Box>
    );
  return <>{children(selected)}</>;
}
