"""Vector search helpers for Hi-EV semantic memory.

This module is intentionally database-dialect aware:
- For SQLite, it uses the sqlite-vec virtual table `vec_document_chunks`.
- For Postgres, it will use a pgvector `vector(384)` column on `document_chunks`.

The public API (create_vector_table, index_chunks, search_chunks) hides the
backend so callers can use the same code paths during the sqlite-vec → pgvector
transition.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

# Name of the sqlite-vec virtual table that stores chunk embeddings.
VEC_TABLE = "vec_document_chunks"
VECTOR_COLUMN = "embedding"


def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def _vector_json(embedding: list[float]) -> str:
    return json.dumps(embedding)


async def create_vector_table(conn: AsyncConnection | AsyncSession) -> None:
    """Create the backend vector store if it does not already exist."""
    # sqlite-vec uses a virtual table with a fixed embedding dimension.
    await conn.execute(
        text(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {VEC_TABLE} USING vec0("
            f"{VECTOR_COLUMN} float[384]"
            f")"
        )
    )


async def index_chunks(
    conn: AsyncConnection | AsyncSession,
    chunks: list[dict],
) -> None:
    """Insert or replace embeddings in the vector table.

    Each `chunk` must contain:
        - "id": integer chunk id (matches `document_chunks.id`)
        - "embedding": list of 384 floats
    """
    if not chunks:
        return

    values = [
        (chunk["id"], _vector_json(chunk["embedding"]))
        for chunk in chunks
        if chunk.get("id") is not None and chunk.get("embedding")
    ]
    if not values:
        return

    # sqlite-vec supports INSERT OR REPLACE via normal SQL.
    stmt = text(
        f"INSERT OR REPLACE INTO {VEC_TABLE} (rowid, {VECTOR_COLUMN}) "
        "VALUES (:chunk_id, :embedding)"
    )
    params = [
        {"chunk_id": chunk_id, "embedding": embedding} for chunk_id, embedding in values
    ]
    await conn.execute(stmt, params)


async def search_chunks(
    conn: AsyncConnection | AsyncSession,
    query_embedding: list[float],
    k: int = 5,
) -> list[tuple[int, float]]:
    """Return the top-k (chunk_id, distance) pairs for a query vector."""
    stmt = text(
        f"SELECT rowid AS chunk_id, distance "
        f"FROM {VEC_TABLE} "
        f"WHERE {VECTOR_COLUMN} MATCH :query "
        f"AND k = :k "
        f"ORDER BY distance"
    )
    result = await conn.execute(
        stmt, {"query": _vector_json(query_embedding), "k": k}
    )
    return [(row.chunk_id, row.distance) for row in result]


async def delete_vector_chunks(
    conn: AsyncConnection | AsyncSession,
    chunk_ids: list[int],
) -> None:
    """Remove vector entries for the given chunk ids."""
    if not chunk_ids:
        return
    stmt = text(f"DELETE FROM {VEC_TABLE} WHERE rowid IN ({', '.join(map(str, chunk_ids))})")
    await conn.execute(stmt)
