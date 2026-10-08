import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errMsg } from "../api";
import type { Repo } from "../types";

type Ctx = {
  repos: Repo[]; selected: Repo | undefined; error: string | null;
  select: (id: string) => void; refresh: () => Promise<void>;
};
const RepoCtx = createContext<Ctx>(null as unknown as Ctx);
export const useRepos = () => useContext(RepoCtx);

export function RepoProvider({ children }: { children: ReactNode }) {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedId, setSelectedId] = useState(localStorage.getItem("repo") ?? "");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRepos(await api<Repo[]>("/api/repositories"));
      setError(null);
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const busy = repos.some((r) => r.index_status === "pending" || r.index_status === "indexing");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [busy, refresh]);

  const value = useMemo<Ctx>(() => ({
    repos, error, refresh,
    selected: repos.find((r) => r.id === selectedId) ?? repos.find((r) => r.index_status === "ready"),
    select: (id) => { localStorage.setItem("repo", id); setSelectedId(id); },
  }), [repos, error, refresh, selectedId]);

  return <RepoCtx.Provider value={value}>{children}</RepoCtx.Provider>;
}
