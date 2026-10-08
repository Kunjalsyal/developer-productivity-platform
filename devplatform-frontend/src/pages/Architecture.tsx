import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { api, errMsg } from "../api";
import { Box, Gate, PageTitle } from "../components/ui";
import type { Graph } from "../types";

function GraphView({ repoId }: { repoId: string }) {
  const [g, setG] = useState<Graph | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Graph>(`/api/repositories/${repoId}/graph`).then(setG).catch((e) => setErr(errMsg(e)));
  }, [repoId]);

  const { nodes, edges } = useMemo(() => {
    if (!g) return { nodes: [] as Node[], edges: [] as Edge[] };
    const groups = [...new Set(g.nodes.map((n) => n.group))];
    const row: Record<string, number> = {};
    const nodes: Node[] = g.nodes.map((n) => {
      const col = groups.indexOf(n.group);
      const r = (row[n.group] = (row[n.group] ?? -1) + 1);
      const linked = sel && g.edges.some((e) => (e.source === sel && e.target === n.id) || (e.target === sel && e.source === n.id));
      const hot = n.id === sel || linked;
      return {
        id: n.id, position: { x: col * 240, y: r * 64 }, data: { label: n.label },
        style: {
          width: 200, fontSize: 12, borderRadius: 6, background: "var(--panel)", color: "var(--ink)",
          border: `${hot ? 2 : 1}px solid ${hot ? "var(--accent)" : "var(--line)"}`,
        },
      } as Node;
    });
    const edges: Edge[] = g.edges.map((e) => {
      const on = sel && (e.source === sel || e.target === sel);
      return { ...e, animated: !!on, style: { stroke: on ? "var(--accent)" : "var(--line)", strokeWidth: on ? 2 : 1 } };
    });
    return { nodes, edges };
  }, [g, sel]);

  if (err) return <Box><span className="text-warn">{err}</span></Box>;
  if (!g) return <p className="text-mute">Loading…</p>;
  if (!g.nodes.length) return <p className="text-mute">No code files were indexed.</p>;
  const info = g.nodes.find((n) => n.id === sel);
  return (
    <>
      <div className="h-[560px] overflow-hidden rounded-lg border border-line bg-panel">
        <ReactFlow nodes={nodes} edges={edges} fitView colorMode="system" nodesConnectable={false}
                   onNodeClick={(_, n) => setSel(n.id)} onPaneClick={() => setSel(null)}>
          <Background /><Controls showInteractive={false} /><MiniMap pannable zoomable />
        </ReactFlow>
      </div>
      <p className="mt-2 text-sm text-mute">{g.nodes.length} files · {g.edges.length} imports. Click a file to highlight what it imports and what imports it.</p>
      {info && <Box className="mt-3"><b className="font-mono text-sm">{info.id}</b> <span className="text-mute">· {info.language} · {info.chunks} chunks</span></Box>}
    </>
  );
}

export default function ArchitecturePage() {
  return (
    <>
      <PageTitle title="Architecture" sub="File-level dependency graph built from import statements in the indexed code. Packages and standard-library imports are left out." />
      <Gate>{(repo) => <GraphView key={repo.id} repoId={repo.id} />}</Gate>
    </>
  );
}
