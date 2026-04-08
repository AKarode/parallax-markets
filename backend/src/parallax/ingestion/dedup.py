"""Semantic deduplication for GDELT events using sentence-transformers.

Uses all-MiniLM-L6-v2 to embed event summaries and drop near-duplicates
above a cosine-similarity threshold.

IMPORTANT: model.encode() is CPU-bound (PyTorch); we wrap it in
asyncio.to_thread() to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Validated threshold: 0.90 not 0.85 — lower values risk merging
# distinct events (e.g., "Iran deploys ships" vs "Iran recalls ambassador").
DEFAULT_THRESHOLD = 0.90


class SemanticDeduplicator:
    """Deduplicate events by comparing sentence embeddings."""

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_THRESHOLD,
        model_name: str = "all-MiniLM-L6-v2",
        model: Any | None = None,
    ) -> None:
        self._threshold = similarity_threshold
        if model is not None:
            self._model = model
        else:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)

    def deduplicate(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Synchronous dedup — suitable for tests and small batches."""
        if len(events) <= 1:
            return events

        summaries = [e.get("summary", "") for e in events]
        embeddings = self._model.encode(summaries, normalize_embeddings=True)

        keep_indices: list[int] = []
        for i, emb in enumerate(embeddings):
            is_dup = False
            for j in keep_indices:
                sim = float(np.dot(emb, embeddings[j]))
                if sim >= self._threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep_indices.append(i)

        return [events[i] for i in keep_indices]

    async def deduplicate_async(
        self, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Async dedup — wraps CPU-bound encode in asyncio.to_thread."""
        if len(events) <= 1:
            return events

        summaries = [e.get("summary", "") for e in events]
        embeddings = await asyncio.to_thread(
            self._model.encode, summaries, normalize_embeddings=True
        )

        keep_indices: list[int] = []
        for i, emb in enumerate(embeddings):
            is_dup = False
            for j in keep_indices:
                sim = float(np.dot(emb, embeddings[j]))
                if sim >= self._threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep_indices.append(i)

        return [events[i] for i in keep_indices]
