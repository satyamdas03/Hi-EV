"""Hi-EV CLI entry point."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import click
from sqlalchemy import select

from ev.db.base import SessionLocal
from ev.db.models import Ingest
from ev.memory.status import build_status_summary
from ev.memory.store import MemoryStore
from ev.tools.alerts_tool import AlertsTool
from ev.tools.brief_tool import BriefTool
from ev.tools.calendar_prep_tool import CalendarPrepTool
from ev.tools.draft_tools import DraftCommitTool, DraftPrTool, DraftReplyTool
from ev.tools.memory_tool import RememberTool
from ev.tools.obligations_tool import ObligationsTool
from ev.tools.people_tool import PeopleTool
from ev.tools.prep_tool import PrepTool
from ev.tools.registry import ToolRegistry
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


@cli.command()
@click.argument("text")
@click.option("--project", help="Project tag")
def remember(text: str, project: str | None):
    """Store a user sentence in semantic memory."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            tool = RememberTool()
            tool.bind_store(store)
            result = await tool.run(text=text, project_name=project)
            click.echo(result["text"])

    asyncio.run(_run())


@cli.group()
def work():
    """Start a focused work session."""


@work.command()
@click.argument("task")
@click.option("--project", required=True, help="Project to work on")
@click.option("--yes", "-y", "confirm", is_flag=True, help="Skip interactive confirmation")
def on(task: str, project: str, confirm: bool):
    """Spawn Claude Code in PROJECT with TASK context."""
    if not confirm:
        confirm = click.confirm(
            f"Spawn Claude Code for '{project}' with task: {task}?",
            default=False,
        )
    if not confirm:
        click.echo("EV: cancelled.")
        return

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


@cli.group()
def draft():
    """Reversible drafting tools."""


@draft.command()
@click.option("--project", required=True, help="Project to draft a commit for")
@click.option("--yes", "-y", "confirm", is_flag=True, help="Skip interactive confirmation")
def commit(project: str, confirm: bool):
    """Draft a commit message from staged changes."""
    if not confirm:
        confirm = click.confirm(
            f"Draft a commit message for '{project}' from staged changes?",
            default=False,
        )
    if not confirm:
        click.echo("EV: cancelled.")
        return

    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(DraftCommitTool())
            result = await registry.get("draft_commit").run(project=project)
            if "error" in result:
                raise click.ClickException(result["error"])
            click.echo(result["draft"])

    asyncio.run(_run())


@draft.command()
@click.option("--project", required=True, help="Project to draft a PR for")
@click.option("--yes", "-y", "confirm", is_flag=True, help="Skip interactive confirmation")
def pr(project: str, confirm: bool):
    """Draft a PR title and body from the branch diff vs main."""
    if not confirm:
        confirm = click.confirm(
            f"Draft a PR for '{project}' from the current branch diff?",
            default=False,
        )
    if not confirm:
        click.echo("EV: cancelled.")
        return

    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(DraftPrTool())
            result = await registry.get("draft_pr").run(project=project)
            if "error" in result:
                raise click.ClickException(result["error"])
            click.echo(result["draft"])

    asyncio.run(_run())


@draft.command()
@click.option("--to", required=True, help="Recipient email address")
@click.option("--subject", required=True, help="Email subject")
@click.option("--snippet", required=True, help="Original message snippet")
@click.option("--yes", "-y", "confirm", is_flag=True, help="Skip interactive confirmation")
def reply(to: str, subject: str, snippet: str, confirm: bool):
    """Draft an email reply."""
    if not confirm:
        confirm = click.confirm(
            f"Draft a reply to '{to}' about '{subject}'?",
            default=False,
        )
    if not confirm:
        click.echo("EV: cancelled.")
        return

    async def _run():
        registry = ToolRegistry(None)
        registry.register(DraftReplyTool())
        result = await registry.get("draft_reply").run(to=to, subject=subject, thread_snippet=snippet)
        click.echo(result["draft"])

    asyncio.run(_run())


@cli.group()
def calendar():
    """Calendar and deadline helpers."""


@calendar.command(name="prep")
@click.argument("time")
def calendar_prep(time: str):
    """Build a prep packet for TIME (ISO or HH:MM)."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(CalendarPrepTool())
            result = await registry.get("calendar_prep").run(time=time)
            click.echo(result["prep"])
            if result["deadlines"]:
                click.echo("\nUpcoming:")
                for d in result["deadlines"]:
                    click.echo(f"  - {d['title']} ({d['due_date']}, {d['priority']})")

    asyncio.run(_run())


@cli.group()
def deadlines():
    """Deadline management."""


@deadlines.command("list")
@click.option("--project", help="Filter by project name")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def list_deadlines(project: str | None, json_output: bool):
    """List upcoming deadlines."""
    async def _run():
        from ev.tools.deadline_watcher import DeadlineWatcherTool

        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(DeadlineWatcherTool())
            result = await registry.get("deadline_watcher").run(project_name=project)
            if json_output:
                click.echo(json.dumps(result, indent=2, default=str))
            else:
                click.echo(f"Deadlines — overdue: {result['counts']['overdue']}, today: {result['counts']['today']}, "
                           f"this week: {result['counts']['this_week']}, future: {result['counts']['future']}")
                for bucket, label in [("overdue", "Overdue"), ("today", "Today"), ("this_week", "This week"), ("future", "Future")]:
                    items = result.get(bucket, [])
                    if items:
                        click.echo(f"\n{label}:")
                        for item in items[:10]:
                            click.echo(f"  - {item['title']} ({item['due_date'][:16]})")

    asyncio.run(_run())


@cli.group()
def people():
    """People EV knows."""


@people.command("list")
@click.option("--project", help="Filter by project")
@click.option("--limit", default=50, help="Maximum rows")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def list_people(project: str | None, limit: int, json_output: bool):
    """List people."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(PeopleTool())
            result = await registry.get("people").run(project_name=project, limit=limit)
            if json_output:
                click.echo(json.dumps(result, indent=2, default=str))
            else:
                click.echo(f"People ({len(result['people'])}):")
                for p in result["people"]:
                    name = p["name"] or p["email"]
                    click.echo(f"  - {name} ({p['email']}) [source: {p['source']}]")

    asyncio.run(_run())


@cli.group()
def obligations():
    """Open obligations."""


@obligations.command("list")
@click.option("--project", help="Filter by project")
@click.option("--status", default="open", help="Filter by status")
@click.option("--overdue", is_flag=True, help="Only overdue")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def list_obligations(project: str | None, status: str, overdue: bool, json_output: bool):
    """List obligations."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(ObligationsTool())
            result = await registry.get("obligations").run(
                project_name=project, status=status, overdue=overdue
            )
            if json_output:
                click.echo(json.dumps(result, indent=2, default=str))
            else:
                click.echo(f"Obligations ({len(result['obligations'])}):")
                for o in result["obligations"]:
                    due = o["due_date"][:16] if o["due_date"] else "no due date"
                    click.echo(f"  - {o['title']} ({due}, {o['status']})")

    asyncio.run(_run())


@cli.command()
@click.option("--project", help="Filter by project")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def alerts(project: str | None, json_output: bool):
    """Show urgent alert digest."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(AlertsTool())
            result = await registry.get("alerts").run(project_name=project)
            if json_output:
                click.echo(json.dumps(result, indent=2, default=str))
            else:
                click.echo(result["digest"])

    asyncio.run(_run())


@cli.group()
def prep():
    """Pre-meeting / pre-deadline prep."""


@prep.command("meeting")
@click.argument("title")
@click.option("--project", help="Project context")
@click.option("--time", help="Target time (ISO or HH:MM)")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def prep_meeting(title: str, project: str | None, time: str | None, json_output: bool):
    """Build prep for a meeting by title."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            registry.register(PrepTool())
            result = await registry.get("prep").run(title=title, project_name=project, time=time)
            if json_output:
                click.echo(json.dumps(result, indent=2, default=str))
            elif result.get("event"):
                click.echo(f"Prep for '{result['event']['title']}' at {result['target'][:16]}:")
                click.echo(result["prep"])
            else:
                click.echo(result["prep"])

    asyncio.run(_run())


@prep.command("today")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def prep_today(json_output: bool):
    """Build prep for all meetings in the next 24 hours."""
    async def _run():
        async with SessionLocal() as session:
            store = MemoryStore(session)
            now = datetime.now(UTC)
            after = now - timedelta(hours=1)
            before = now + timedelta(hours=24)
            stmt = select(Ingest).where(Ingest.source == "calendar_events").order_by(Ingest.updated_at)
            result = await store.session.execute(stmt)
            all_events = result.scalars().all()

            def _event_dt(event: Ingest) -> datetime:
                dt = PrepTool._parse_event_time(event.content or "")
                if dt is None:
                    dt = event.updated_at or datetime.now(UTC)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt

            events = [e for e in all_events if after <= _event_dt(e) <= before]
            if not events:
                click.echo("EV: no meetings in the next 24 hours.")
                return

            registry = ToolRegistry(store)
            registry.register(PrepTool())
            preps = []
            for event in events:
                title = (event.content or "").splitlines()[0].replace("Event: ", "") if event.content else "Meeting"
                event_dt = _event_dt(event)
                prep_result = await registry.get("prep").run(title=title, time=event_dt.isoformat())
                preps.append(prep_result)
                if not json_output:
                    click.echo(f"\n--- {title} ---")
                    click.echo(prep_result["prep"])
            if json_output:
                click.echo(json.dumps({"preps": preps}, indent=2, default=str))

    asyncio.run(_run())
