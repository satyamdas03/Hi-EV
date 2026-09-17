"""Local offline embedding model for Hi-EV semantic memory.

Defaults to `all-MiniLM-L6-v2` via sentence-transformers. The model is downloaded
on first use to the standard Hugging Face cache directory and runs entirely on the
local RTX 5060 laptop.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ev.config import Settings, get_settings

# Known dimension for the default model. Other models report their own dimension.
DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DIMENSION = 384


class EmbeddingModel:
    """Thin, lazy-loading wrapper around sentence-transformers."""

    def __init__(self, model_name: str | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.embedding_model or DEFAULT_MODEL
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding dimension for the loaded model."""
        if self.model_name == DEFAULT_MODEL:
            return DEFAULT_DIMENSION
        return self._load().get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts into dense vectors."""
        if not texts:
            return []
        model = self._load()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def encode_one(self, text: str) -> list[float]:
        """Encode a single text into a dense vector."""
        return self.encode([text])[0]


@lru_cache
def get_embedding_model(model_name: str | None = None, settings: Settings | None = None) -> EmbeddingModel:
    """Return the shared embedding model instance."""
    return EmbeddingModel(model_name=model_name, settings=settings)
