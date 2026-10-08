"""Measure report metrics against a running API: precision@k, latency, explainer citation accuracy.

  python scripts/eval_search.py --api http://localhost:8000 --repo <uuid> \
      --queries eval/queries.example.json --checkout /path/to/local/clone

queries.json: [{"query": "...", "relevant": ["path/file.py::func_name", "other/file.ts"]}]
A hit is relevant if its "file::name" or its file path is listed.
Citation accuracy (needs --checkout, run on the same commit): a citation counts as correct when the
cited line range of the local file equals the text the API returned.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

import httpx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--checkout")
    ap.add_argument("--api-key")
    ap.add_argument("--explain", action="store_true", help="also run /explain for latency + citation accuracy")
    a = ap.parse_args()
    headers = {"X-API-Key": a.api_key} if a.api_key else {}
    base = f"{a.api}/api/repositories/{a.repo}"
    queries = json.loads(Path(a.queries).read_text())
    client = httpx.Client(headers=headers, timeout=60)

    precisions, lat, ex_lat, ok, total, low = [], [], [], 0, 0, 0
    for q in queries:
        t0 = time.perf_counter()
        res = client.post(f"{base}/search", json={"query": q["query"], "top_k": a.k}).json()["results"]
        lat.append(time.perf_counter() - t0)
        rel = set(q["relevant"])
        good = sum(1 for h in res if f"{h['file_path']}::{h['name']}" in rel or h["file_path"] in rel)
        precisions.append(good / a.k)
        print(f"P@{a.k}={good / a.k:.2f}  {q['query']}")
        if a.explain:
            t0 = time.perf_counter()
            r = client.post(f"{base}/explain", json={"query": q["query"]}).json()
            ex_lat.append(time.perf_counter() - t0)
            low += r["low_confidence"]
            for c in r["citations"]:
                if a.checkout and c["source"] == "code":
                    f = Path(a.checkout) / c["file_path"]
                    total += 1
                    if f.exists():
                        got = "\n".join(f.read_text().split("\n")[c["start_line"] - 1:c["end_line"]])
                        ok += got == c["content"]

    print(f"\nprecision@{a.k}: {statistics.mean(precisions):.3f}  (target >= 0.7)")
    print(f"search latency: median {statistics.median(lat) * 1000:.0f} ms (target <= 2000)")
    if a.explain:
        print(f"explainer latency: median {statistics.median(ex_lat) * 1000:.0f} ms (target <= 6000)")
        print(f"low-confidence rate: {low}/{len(queries)}")
        if total:
            print(f"citation accuracy: {ok}/{total} = {ok / total:.1%} (target >= 90%)")


if __name__ == "__main__":
    main()
