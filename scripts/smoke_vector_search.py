"""Smoke test for local semantic memory.

Creates a few DocumentChunk rows, indexes their embeddings with sqlite-vec,
and runs a similarity search. This verifies the end-to-end vector path
without any Postgres install.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import delete, select

from ev.db.base import Base, SessionLocal, engine
from ev.db.models import DocumentChunk
from ev.db.vector import (
    create_vector_table,
    delete_vector_chunks,
    index_chunks,
    search_chunks,
)
from ev.embeddings import get_embedding_model


async def main() -> None:
    model = get_embedding_model()
    dim = model.dimension
    print(f"Embedding model: {model.model_name}, dimension: {dim}")

    # Create structured metadata table and vector table.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await create_vector_table(conn)

    # Use a fresh run id so repeated smoke tests do not collide.
    run_id = uuid.uuid4().hex[:8]

    samples = [
        "RoboCAD is a generative CAD platform for robotics.",
        "Hi-EV is a personal AI operating system that runs locally.",
        "The RTX 5060 laptop can run local embeddings and LLMs.",
    ]
    embeddings = model.encode(samples)

    async with SessionLocal() as session:
        # Clean up any previous smoke-test chunks and their vectors.
        prev = await session.execute(
            select(DocumentChunk.id).where(DocumentChunk.source == "smoke")
        )
        prev_ids = list(prev.scalars().all())
        if prev_ids:
            await delete_vector_chunks(session, prev_ids)
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.source == "smoke")
            )
            await session.commit()

        chunks = []
        for i, (text, embedding) in enumerate(zip(samples, embeddings)):
            chunk = DocumentChunk(
                source="smoke",
                source_id=f"smoke:{run_id}:{i}",
                chunk_index=i,
                text=text,
            )
            session.add(chunk)
            chunks.append((chunk, embedding))
        await session.commit()

        # Refresh to get autoincrement ids.
        for chunk, _embedding in chunks:
            await session.refresh(chunk)

        vector_payload = [
            {"id": chunk.id, "embedding": embedding}
            for chunk, embedding in chunks
        ]
        await index_chunks(session, vector_payload)
        await session.commit()

        query = "local AI assistant"
        query_embedding = model.encode_one(query)
        results = await search_chunks(session, query_embedding, k=2)

        print(f"\nQuery: {query!r}")
        for chunk_id, distance in results:
            row = await session.execute(
                select(DocumentChunk).where(DocumentChunk.id == chunk_id)
            )
            chunk = row.scalar_one()
            print(f"  [{distance:.4f}] {chunk.text}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
