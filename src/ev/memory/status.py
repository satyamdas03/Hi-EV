"""Project status summary builder."""

import re

from sqlalchemy import desc, select

from ev.db.models import Ingest, Project


_PHASE_RE = re.compile(r"(?i)\bphase\s+(\d+[A-Z]?)\b")


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

    phase = project.current_phase or _infer_phase(commits, notes)

    def to_dict(r):
        return {"source": r.source, "source_id": r.source_id, "content": r.content, "updated_at": r.updated_at.isoformat()}

    latest = rows[0].updated_at if rows else None
    open_issue_count = await store.count_open_issues(project_name)
    open_pr_count = await store.count_open_prs(project_name)
    recent_note_count = len(await store.recent_notes(project_name, limit=5))
    summary_text = _make_summary_text(project, phase, commits, open_issue_count, open_pr_count, recent_note_count)

    return {
        "name": project.name,
        "phase": phase,
        "latest_commits": [to_dict(c) for c in commits],
        "open_issues": [to_dict(i) for i in issues],
        "open_prs": [to_dict(p) for p in prs],
        "recent_notes": [to_dict(n) for n in notes],
        "open_issue_count": open_issue_count,
        "open_pr_count": open_pr_count,
        "recent_note_count": recent_note_count,
        "last_activity": latest.isoformat() if latest else None,
        "summary_text": summary_text,
    }


def _infer_phase(commits: list[Ingest], notes: list[Ingest]) -> str | None:
    for record in (*commits, *notes):
        match = _PHASE_RE.search(record.content or "")
        if match:
            return f"Phase {match.group(1)}"
    return None


def _make_summary_text(project, phase, commits, open_issue_count: int, open_pr_count: int, recent_note_count: int):
    parts = [f"{project.name} is at {phase or 'unknown phase'}."]
    if commits:
        parts.append(f"Latest commit: {commits[0].content.splitlines()[0][:80]}.")
    if open_issue_count:
        parts.append(f"{open_issue_count} open issue(s).")
    if open_pr_count:
        parts.append(f"{open_pr_count} open PR(s).")
    if recent_note_count:
        parts.append(f"{recent_note_count} recent note(s).")
    return " ".join(parts)
