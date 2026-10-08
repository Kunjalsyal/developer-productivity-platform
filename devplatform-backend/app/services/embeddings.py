from __future__ import annotations

import math
import re
import threading
import zlib
from functools import lru_cache
from typing import Protocol

from ..config import get_settings

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def code_tokens(text: str) -> list[str]:
    """Split snake_case / camelCase identifiers into lowercase word tokens."""
    return [p.lower() for w in _WORD.findall(text) for p in _CAMEL.split(w) if p]


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic feature-hashing embedder. Lexical only — for tests and offline dev."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            v = [0.0] * self.dim
            toks = code_tokens(text)
            for f in toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]:
                h = zlib.crc32(f.encode())
                v[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


class SentenceTransformerEmbedder:
    def __init__(self, model: str, dim: int):
        self.dim, self._name, self._model = dim, model, None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                m = SentenceTransformer(self._name)
                actual = m.get_sentence_embedding_dimension()
                if actual != self.dim:
                    raise RuntimeError(
                        f"{self._name} outputs {actual}-d vectors but EMBEDDING_DIM={self.dim}; "
                        "set EMBEDDING_DIM to match and recreate the chunks table."
                    )
                self._model = m
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._load().encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_backend == "hash":
        return HashEmbedder(s.embedding_dim)
    return SentenceTransformerEmbedder(s.embedding_model, s.embedding_dim)
