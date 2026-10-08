from __future__ import annotations

import io
import posixpath
import re
import tarfile
from dataclasses import dataclass

import httpx

from ..config import get_settings
from ..services.chunker import CODE_EXT, DOC_EXT
from .base import Connector, ConnectorError, SourceDocument

API = "https://api.github.com"
IGNORED_DIRS = {".git", "node_modules", "dist", "build", "venv", ".venv", "__pycache__", "vendor",
                ".next", "coverage", "site-packages", ".tox", ".mypy_cache"}
_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
_SHORT = re.compile(r"^([\w.-]+)/([\w.-]+)$")


def parse_repo_url(url: str) -> tuple[str, str]:
    s = url.strip()
    m = _URL.match(s) or _SHORT.match(s)
    if not m:
        raise ValueError("expected a GitHub repo URL like https://github.com/owner/name")
    return m.group(1), m.group(2)


@dataclass
class RepoRef:
    owner: str
    name: str
    branch: str | None = None


@dataclass
class DiscussionItem:
    kind: str  # pr_body | comment | review_comment | issue
    ref: str
    author: str | None
    text: str
    url: str | None


class GitHubConnector(Connector):
    def __init__(self, token: str | None = None, client: httpx.Client | None = None):
        self.token = token
        self._client = client or httpx.Client(timeout=30)

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, accept: str = "application/vnd.github+json", params=None, timeout: float = 30):
        headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "devplatform"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        r = self._client.get(f"{API}{path}", headers=headers, params=params, timeout=timeout,
                             follow_redirects=True)
        if r.status_code == 404:
            raise ConnectorError("GitHub 404: not found, or the token has no access to it", 404)
        if r.status_code in (401, 403):
            limited = r.headers.get("x-ratelimit-remaining") == "0"
            raise ConnectorError("GitHub rate limit exceeded" if limited else
                                 "GitHub rejected the token (401/403); check GITHUB_TOKEN", r.status_code)
        if r.status_code >= 400:
            raise ConnectorError(f"GitHub {r.status_code}: {r.text[:200]}", r.status_code)
        return r

    # -------- repository content
    def get_repo(self, owner: str, name: str) -> dict:
        return self._get(f"/repos/{owner}/{name}").json()

    def head_sha(self, owner: str, name: str, ref: str) -> str:
        return self._get(f"/repos/{owner}/{name}/commits/{ref}", accept="application/vnd.github.sha").text.strip()

    def fetch_context(self, repo: RepoRef) -> list[SourceDocument]:
        s = get_settings()
        ref = repo.branch or self.get_repo(repo.owner, repo.name)["default_branch"]
        resp = self._get(f"/repos/{repo.owner}/{repo.name}/tarball/{ref}", timeout=180)
        docs: list[SourceDocument] = []
        with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
            for m in tar:
                if not m.isfile() or m.size > s.max_file_bytes:
                    continue
                parts = m.name.split("/", 1)
                if len(parts) < 2:
                    continue
                path = parts[1]
                if any(p in IGNORED_DIRS for p in path.split("/")[:-1]) or path.endswith((".min.js", ".d.ts")):
                    continue
                ext = posixpath.splitext(path)[1].lower()
                kind = "code" if ext in CODE_EXT else "doc" if ext in DOC_EXT else None
                if kind is None:
                    continue
                try:
                    text = tar.extractfile(m).read().decode("utf-8")
                except UnicodeDecodeError:
                    continue
                docs.append(SourceDocument(
                    path, text, kind, f"https://github.com/{repo.owner}/{repo.name}/blob/{ref}/{path}"))
        return docs

    # -------- pull requests
    def list_open_prs(self, owner: str, name: str, limit: int = 30) -> list[dict]:
        return self._get(f"/repos/{owner}/{name}/pulls",
                         params={"state": "open", "per_page": limit, "sort": "updated"}).json()

    def get_pr(self, owner: str, name: str, number: int) -> dict:
        return self._get(f"/repos/{owner}/{name}/pulls/{number}").json()

    def get_pr_diff(self, owner: str, name: str, number: int) -> str:
        return self._get(f"/repos/{owner}/{name}/pulls/{number}", accept="application/vnd.github.diff").text

    def get_pr_discussion(self, owner: str, name: str, pr: dict) -> list[DiscussionItem]:
        n = pr["number"]
        items: list[DiscussionItem] = []
        body = (pr.get("body") or "").strip()
        if body:
            items.append(DiscussionItem("pr_body", f"#{n}", (pr.get("user") or {}).get("login"),
                                        body[:3000], pr.get("html_url")))
        for c in self._get(f"/repos/{owner}/{name}/issues/{n}/comments", params={"per_page": 20}).json():
            items.append(DiscussionItem("comment", f"#{n}", (c.get("user") or {}).get("login"),
                                        (c.get("body") or "")[:1500], c.get("html_url")))
        for c in self._get(f"/repos/{owner}/{name}/pulls/{n}/comments", params={"per_page": 20}).json():
            items.append(DiscussionItem("review_comment", f"#{n}", (c.get("user") or {}).get("login"),
                                        f"[{c.get('path')}] {(c.get('body') or '')[:1000]}", c.get("html_url")))
        linked = {int(x) for x in re.findall(r"#(\d+)", body)} - {n}
        for num in sorted(linked)[:5]:
            try:
                issue = self._get(f"/repos/{owner}/{name}/issues/{num}").json()
            except ConnectorError:
                continue
            items.append(DiscussionItem("issue", f"#{num}", (issue.get("user") or {}).get("login"),
                                        f"{issue.get('title')}\n{(issue.get('body') or '')[:1200]}",
                                        issue.get("html_url")))
        return items
