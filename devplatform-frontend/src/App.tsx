import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Architecture from "./pages/Architecture";
import Dashboard from "./pages/Dashboard";
import Explain from "./pages/Explain";
import Pulls from "./pages/Pulls";
import Search from "./pages/Search";
import { RepoProvider } from "./state/RepoContext";

export default function App() {
  return (
    <RepoProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="search" element={<Search />} />
            <Route path="explain" element={<Explain />} />
            <Route path="pulls" element={<Pulls />} />
            <Route path="architecture" element={<Architecture />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </RepoProvider>
  );
}
