"""Project status summary builder."""

from sqlalchemy import desc, select

from ev.db.models import Ingest, Project


async def build_status_summary(store, project_name: str) -> dict:
    """Return a structured status summary for a named project."""
    result = await store.session.execute(select(Project).where(Project.name == project_name))
    project = result.scalar_one_or_none()
    if project is None:
        return {"name": project_name, "phase": None, "error": "Project not found in memory"}

    tag = project_name.lower()
    stmt = select(Ingest).where(Ingest.project_tag == tag).order_by(desc(Ingest.updated_at))
    result = await store.session.execute(stmt)
    rows = result.scalars().all()

    commits = [r for r in rows if r.source == "github_commits"][:5]
    issues = [r for r in rows if r.source == "github_issues"][:5]
    prs = [r for r in rows if r.source == "github_prs"][:5]
    notes = [r for r in rows if r.source == "notes"][:3]

    def to_dict(r):
        return {"source": r.source, "source_id": r.source_id, "content": r.content, "updated_at": r.updated_at.isoformat()}

    latest = rows[0].updated_at if rows else None
    summary_text = _make_summary_text(project, commits, issues, prs, notes)

    return {
        "name": project.name,
        "phase": project.current_phase,
        "latest_commits": [to_dict(c) for c in commits],
        "open_issues": [to_dict(i) for i in issues],
        "open_prs": [to_dict(p) for p in prs],
        "recent_notes": [to_dict(n) for n in notes],
        "last_activity": latest.isoformat() if latest else None,
        "summary_text": summary_text,
    }


def _make_summary_text(project, commits, issues, prs, notes):
    parts = [f"{project.name} is at {project.current_phase or 'unknown phase'}."]
    if commits:
        parts.append(f"Latest commit: {commits[0].content.splitlines()[0][:80]}.")
    if issues:
        parts.append(f"{len(issues)} recent issue(s).")
    if prs:
        parts.append(f"{len(prs)} recent PR(s).")
    if notes:
        parts.append(f"{len(notes)} recent note(s).")
    return " ".join(parts)
