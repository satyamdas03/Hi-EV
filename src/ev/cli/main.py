"""Hi-EV CLI entry point."""

import asyncio

import click

from ev.db.base import SessionLocal
from ev.memory.store import MemoryStore
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool


@click.group()
def cli():
    """Hi-EV — personal AI operating system."""


@cli.command()
@click.argument("project")
def status(project: str):
    """Show a one-paragraph status update for PROJECT."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(StatusTool())
            result = await registry.get("status").run(project=project)
            click.echo(result)

    asyncio.run(_run())
