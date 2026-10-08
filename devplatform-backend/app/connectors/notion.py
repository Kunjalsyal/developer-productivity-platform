from __future__ import annotations

import time

import httpx

from .base import Connector, ConnectorError, SourceDocument

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


class NotionConnector(Connector):
    """Reads pages the integration was shared with (or a page subtree) into plain text."""

    def __init__(self, token: str, root_id: str | None = None, client: httpx.Client | None = None,
                 max_pages: int = 200):
        if not token:
            raise ConnectorError("NOTION_TOKEN is not configured")
        self.token, self.root_id, self.max_pages = token, root_id, max_pages
        self._client = client or httpx.Client(timeout=30)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kw) -> dict:
        headers = {"Authorization": f"Bearer {self.token}", "Notion-Version": VERSION}
        for attempt in range(3):
            r = self._client.request(method, f"{API}{path}", headers=headers, **kw)
            if r.status_code == 429 and attempt < 2:
                time.sleep(float(r.headers.get("Retry-After", "1")))
                continue
            if r.status_code >= 400:
                raise ConnectorError(f"Notion {r.status_code}: {r.text[:200]}", r.status_code)
            return r.json()
        raise ConnectorError("Notion rate limit exceeded", 429)

    def _paginate(self, method: str, path: str, body: dict | None = None, params: dict | None = None):
        cursor = None
        while True:
            kw: dict = {}
            if method == "POST":
                kw["json"] = {**(body or {}), **({"start_cursor": cursor} if cursor else {})}
            else:
                kw["params"] = {**(params or {}), **({"start_cursor": cursor} if cursor else {})}
            data = self._request(method, path, **kw)
            yield from data.get("results", [])
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")

    @staticmethod
    def _rich(rt: list[dict]) -> str:
        return "".join(t.get("plain_text", "") for t in rt)

    @staticmethod
    def _title(page: dict) -> str:
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in prop["title"]) or "Untitled"
        return "Untitled"

    def _blocks(self, block_id: str, depth: int, lines: list[str], child_pages: list[str]) -> None:
        for b in self._paginate("GET", f"/blocks/{block_id}/children", params={"page_size": 100}):
            t = b["type"]
            data = b.get(t, {})
            text = self._rich(data.get("rich_text", []))
            if t == "child_page":
                child_pages.append(b["id"])
                continue
            if t in ("heading_1", "heading_2", "heading_3"):
                lines.append("#" * int(t[-1]) + " " + text)
            elif t == "bulleted_list_item":
                lines.append("- " + text)
            elif t == "numbered_list_item":
                lines.append("1. " + text)
            elif t == "to_do":
                lines.append(("- [x] " if data.get("checked") else "- [ ] ") + text)
            elif t == "quote":
                lines.append("> " + text)
            elif t == "code":
                lines.append("```\n" + text + "\n```")
            elif text:
                lines.append(text)
            if b.get("has_children") and depth < 4:
                self._blocks(b["id"], depth + 1, lines, child_pages)

    def fetch_context(self, repo=None) -> list[SourceDocument]:
        if self.root_id:
            pages = [self._request("GET", f"/pages/{self.root_id}")]
        else:
            pages = list(self._paginate(
                "POST", "/search", body={"filter": {"property": "object", "value": "page"}, "page_size": 100}))
        docs: list[SourceDocument] = []
        seen: set[str] = set()
        while pages and len(docs) < self.max_pages:
            page = pages.pop(0)
            if page["id"] in seen:
                continue
            seen.add(page["id"])
            lines: list[str] = []
            kids: list[str] = []
            self._blocks(page["id"], 0, lines, kids)
            title = self._title(page)
            docs.append(SourceDocument(f"notion:{title}", f"# {title}\n" + "\n".join(lines), "notion",
                                       page.get("url"), title))
            if self.root_id:
                pages.extend(self._request("GET", f"/pages/{k}") for k in kids)
        return docs
