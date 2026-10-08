export type Status = "pending" | "indexing" | "ready" | "failed";

export type Repo = {
  id: string; url: string; owner: string; name: string; branch: string | null;
  commit_sha: string | null; include_notion: boolean; index_status: Status;
  index_error: string | null; file_count: number; chunk_count: number;
  created_at: string; last_indexed_at: string | null;
};

export type Hit = {
  chunk_id: number; file_path: string; start_line: number; end_line: number; name: string;
  kind: string; language: string | null; source: string; url: string | null;
  similarity: number; score: number; content: string;
};

export type Citation = Hit & { index: number | null };

export type Explain = {
  answer: string; low_confidence: boolean; reason: string | null; confidence: number;
  citations: Citation[]; related: Citation[]; unverified_terms: string[]; latency_ms: number;
};

export type PRItem = {
  number: number; title: string; author: string | null; url: string; updated_at: string; summarized: boolean;
};

export type PRSummary = {
  pr_number: number; title: string; url: string | null; head_sha: string; summary: string; why: string;
  review_notes: string[]; cached: boolean;
  related: {
    changed_files: string[];
    discussion: { kind: string; ref: string; author: string | null; url: string | null; excerpt: string }[];
    docs: { title: string; path: string; url: string | null; similarity: number }[];
  };
};

export type Graph = {
  nodes: { id: string; label: string; group: string; language: string | null; chunks: number }[];
  edges: { id: string; source: string; target: string }[];
};
