"""End-to-end smoke test for Hi-EV semantic memory.

Stores a user memory, searches it, and verifies the result is returned.
Run after `python scripts/setup_sqlite_vec.py`.
"""

import asyncio
import sys

from ev.db.base import SessionLocal
from ev.memory.store import MemoryStore
from ev.tools.memory_tool import MemoryTool, RememberTool


async def main() -> int:
    async with SessionLocal() as session:
        store = MemoryStore(session)

        remember = RememberTool()
        remember.bind_store(store)
        search = MemoryTool()
        search.bind_store(store)

        print("Storing memory...")
        result = await remember.run(
            text="RoboCAD is targeting full-robot synthesis in Phase 23.",
            project_name="robocad",
        )
        print(result["text"])

        print("\nSearching memory...")
        result = await search.run(query="what phase is RoboCAD in?", project_name="robocad", k=3)
        print(result["text"])

        if any("Phase 23" in chunk["text"] for chunk in result["chunks"]):
            print("\n[OK] Semantic memory smoke test passed.")
            return 0

        print("\n[FAIL] Semantic memory smoke test failed: expected Phase 23 in results.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
