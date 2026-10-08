import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .connectors.github import parse_repo_url

Source = Literal["code", "doc", "notion"]


class RepoCreate(BaseModel):
    url: str
    branch: str | None = None
    include_notion: bool = False
    notion_root_id: str | None = None

    @field_validator("url")
    @classmethod
    def _valid_url(cls, v: str) -> str:
        parse_repo_url(v)
        return v.strip()


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    url: str
    owner: str
    name: str
    branch: str | None
    commit_sha: str | None
    include_notion: bool
    index_status: str
    index_error: str | None
    file_count: int
    chunk_count: int
    created_at: datetime
    last_indexed_at: datetime | None


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(5, ge=1, le=25)
    sources: list[Source] | None = None
    languages: list[Literal["python", "javascript", "typescript"]] | None = None


class SearchHit(BaseModel):
    chunk_id: int
    file_path: str
    start_line: int
    end_line: int
    name: str
    kind: str
    language: str | None
    source: str
    url: str | None
    similarity: float
    score: float
    content: str


class SearchResponse(BaseModel):
    results: list[SearchHit]
    latency_ms: int


class ExplainRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)


class CitationOut(SearchHit):
    index: int | None = None  # the [n] marker in the answer; None for related-but-uncited sources


class ExplainResponse(BaseModel):
    answer: str
    low_confidence: bool
    reason: str | None
    confidence: float
    citations: list[CitationOut]
    related: list[CitationOut]
    unverified_terms: list[str]
    latency_ms: int


class PRListItem(BaseModel):
    number: int
    title: str
    author: str | None
    url: str
    updated_at: str
    summarized: bool


class PRSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pr_number: int
    title: str
    url: str | None
    head_sha: str
    summary: str
    why: str
    review_notes: list[str]
    related: dict
    cached: bool = False


class GraphNode(BaseModel):
    id: str
    label: str
    group: str
    language: str | None
    chunks: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
