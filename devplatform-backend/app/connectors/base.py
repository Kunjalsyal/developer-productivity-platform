from abc import ABC, abstractmethod
from dataclasses import dataclass


class ConnectorError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class SourceDocument:
    path: str
    content: str
    kind: str  # code | doc | notion
    url: str | None = None
    title: str | None = None


class Connector(ABC):
    """Matches the report's Connector interface: fetchContext(repo)."""

    @abstractmethod
    def fetch_context(self, repo) -> list[SourceDocument]: ...
