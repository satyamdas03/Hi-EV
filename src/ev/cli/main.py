"""Hi-EV CLI entry point."""

import asyncio
import json

import click

from ev.db.base import SessionLocal
from ev.memory.status import build_status_summary
from ev.memory.store import MemoryStore
from ev.tools.registry import ToolRegistry
from ev.tools.brief_tool import BriefTool
from ev.tools.research_tool import ResearchTool
from ev.tools.status_tool import StatusTool
from ev.tools.work_tool import WorkTool


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


@cli.command()
def brief():
    """Show a cross-project status brief."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(BriefTool())
            result = await registry.get("brief").run()
            click.echo(result)

    asyncio.run(_run())


@cli.command()
@click.argument("query")
def research(query: str):
    """Search the web and synthesize a cited answer for QUERY."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(ResearchTool())
            result = await registry.get("research").run(query=query)
            click.echo(result["answer"])
            if result["sources"]:
                click.echo("\nSources:")
                for idx, source in enumerate(result["sources"], 1):
                    click.echo(f"  [{idx}] {source['title']} — {source['url']}")

    asyncio.run(_run())


@cli.group()
def work():
    """Start a focused work session."""


@work.command()
@click.argument("task")
@click.option("--project", required=True, help="Project to work on")
def on(task: str, project: str):
    """Spawn Claude Code in PROJECT with TASK context."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(WorkTool())
            result = await registry.get("work_on").run(project=project, task=task)
            if "error" in result:
                click.echo(f"EV: {result['error']}", err=True)
                raise click.ClickException(result["error"])
            click.echo(f"Spawned Claude Code for {result['project']} (pid {result['pid']}):")
            click.echo(result["context_preview"])

    asyncio.run(_run())
