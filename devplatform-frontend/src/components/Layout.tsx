import { Code2, GitPullRequest, LayoutDashboard, MessageSquareText, Network, Search } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useRepos } from "../state/RepoContext";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/search", label: "Code search", icon: Search },
  { to: "/explain", label: "Explainer", icon: MessageSquareText },
  { to: "/pulls", label: "Pull requests", icon: GitPullRequest },
  { to: "/architecture", label: "Architecture", icon: Network },
];

export default function Layout() {
  const { repos, selected, select } = useRepos();
  const ready = repos.filter((r) => r.index_status === "ready");
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <nav className="flex shrink-0 flex-col gap-1 border-b border-line p-3 md:sticky md:top-0 md:h-screen md:w-60 md:border-b-0 md:border-r md:p-4">
        <div className="mb-3 flex items-center gap-2 px-2 font-semibold leading-tight">
          <Code2 size={20} className="text-accent" /> Developer Productivity Platform
        </div>
        <label className="px-2 text-xs text-mute" htmlFor="repo">Repository</label>
        <select
          id="repo" value={selected?.id ?? ""} onChange={(e) => select(e.target.value)} disabled={!ready.length}
          className="mx-2 mb-3 rounded-md border border-line bg-bg px-2 py-1.5 text-sm"
        >
          {!ready.length && <option value="">none indexed</option>}
          {ready.map((r) => <option key={r.id} value={r.id}>{r.owner}/{r.name}</option>)}
        </select>
        <div className="flex flex-wrap gap-1 md:flex-col">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to} to={to} end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-accent text-accent-ink" : "text-mute hover:bg-code"}`}
            >
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="min-w-0 max-w-5xl flex-1 p-4 md:p-8"><Outlet /></main>
    </div>
  );
}
