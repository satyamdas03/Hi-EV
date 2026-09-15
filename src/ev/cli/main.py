"""Hi-EV CLI entry point."""

import asyncio
import json

import click

from ev.db.base import SessionLocal
from ev.memory.status import build_status_summary
from ev.memory.store import MemoryStore
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool


@click.group()
def cli():
    """Hi-EV — personal AI operating system."""


@cli.command()
@click.argument("project")
@click.option("--json", "json_output", is_flag=True, help="Emit structured JSON instead of a paragraph.")
def status(project: str, json_output: bool):
    """Show a one-paragraph status update for PROJECT."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            if json_output:
                summary = await build_status_summary(store, project)
                click.echo(json.dumps(summary, indent=2, default=str))
            else:
                registry = ToolRegistry(store)
                registry.register(StatusTool())
                result = await registry.get("status").run(project=project)
                click.echo(result)

    asyncio.run(_run())
