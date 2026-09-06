import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass
class RawDocument:
    title: str
    content: str
    url: str | None = None
    publisher: str | None = None
    source_type: str = "official_provider"
    authority_level: int = 1
    jurisdiction: str | None = "Pakistan"
    provider: str | None = None
    topics: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


class KnowledgeCrawler(Protocol):
    async def crawl(self, source: dict) -> list[RawDocument]: ...
