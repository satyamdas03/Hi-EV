"""Base abstraction for ingestion sources."""

from abc import ABC, abstractmethod
from typing import Any


class IngestionSource(ABC):
    """A generic source that produces normalized ingest records."""

    @abstractmethod
    def ingest(self) -> list[dict[str, Any]]:
        """Return a list of normalized memory records."""
        raise NotImplementedError
