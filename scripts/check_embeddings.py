#!/usr/bin/env python3
"""Smoke-test the local embedding model for Hi-EV semantic memory."""

import asyncio

from ev.embeddings import get_embedding_model


async def main():
    print("Loading local embedding model...")
    model = get_embedding_model()
    samples = [
        "RoboCAD is a generative robotics CAD platform.",
        "Hi-EV is a local-first personal AI operating system.",
        "What are the open issues for the current phase?",
    ]
    vectors = model.encode(samples)
    print(f"Model: {model.model_name}")
    print(f"Dimension: {model.dimension}")
    print(f"Encoded {len(vectors)} sample(s).")
    print("First vector head:", vectors[0][:5])


if __name__ == "__main__":
    asyncio.run(main())
