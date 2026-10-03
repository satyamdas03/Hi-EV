"""Tests for the Phase F plugin registry and skill scaffolding."""


import pytest

from ev.core import RegistryBase, registry
from ev.core.component import AgentContext, BaseTool
from ev.skills.manager import SkillManager
from ev.skills.parser import parse_skill_file
from ev.skills.tool_adapter import SkillTool
from ev.tools.registry import ToolRegistry


def test_registry_decorator_registers_tool_class(tmp_path):
    reg = RegistryBase[BaseTool]("test_tool")

    @reg.register("demo")
    class DemoTool(BaseTool):
        name = "demo"
        tier = 0
        description = "demo tool"

        async def run(self, **kwargs):
            return "ok"

    assert reg.has("demo")
    instance = reg.get("demo")
    assert isinstance(instance, DemoTool)


def test_global_tool_registry_auto_discovers_tools():
    # Importing ev.tools triggers discovery.
    import ev.tools  # noqa: F401

    names = registry["tool"].list()
    for expected in ("status", "brief", "memory", "remember", "research", "work_on"):
        assert expected in names, f"Missing tool {expected} in {names}"


def test_tool_registry_get_finds_tool_without_manual_registration():
    # Use a dummy store; status tool only needs store to exist for bind_store.
    from ev.memory.store import MemoryStore

    class FakeSession:
        pass

    # MemoryStore expects an async session; we only check tool lookup here.
    store = MemoryStore(None)
    tr = ToolRegistry(store)
    tool = tr.get("status")
    assert tool.name == "status"


@pytest.mark.anyio
async def test_simple_agent_returns_text(monkeypatch):
    from ev.agents.simple import SimpleAgent

    calls = []

    class FakeClient:
        async def complete(self, messages, **kwargs):
            calls.append(messages)
            return "hello"

    agent = SimpleAgent(client=FakeClient())
    result = await agent.run("hi", AgentContext())
    assert result.text == "hello"
    assert result.route == "fast"


def test_skill_manifest_validate():
    from ev.skills.types import SkillManifest, SkillParameter

    manifest = SkillManifest(
        name="summarize_notes",
        parameters=[
            SkillParameter(name="project", required=True),
            SkillParameter(name="k", required=False, default=3),
        ],
    )
    ok, missing = manifest.validate({"project": "RoboCAD"})
    assert ok
    assert not missing

    ok, missing = manifest.validate({})
    assert not ok
    assert missing == ["project"]


def test_skill_parser_reads_frontmatter(tmp_path):
    skill_dir = tmp_path / "summarize_notes"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "name: summarize_notes\n"
        "description: Summarize notes for a project\n"
        "version: 0.1.0\n"
        "parameters:\n"
        "  project:\n"
        "    type: string\n"
        "    description: Project name\n"
        "    required: true\n"
        "---\n"
        "# Summarize notes\n\n"
        "Summarize the latest notes for {project}.\n"
    )

    manifest = parse_skill_file(skill_file)
    assert manifest is not None
    assert manifest.name == "summarize_notes"
    assert manifest.parameter_names == ["project"]
    assert "{project}" in manifest.body


@pytest.mark.anyio
async def test_skill_tool_render_prompt(monkeypatch):
    from ev.skills.types import SkillManifest, SkillParameter

    manifest = SkillManifest(
        name="hello",
        parameters=[SkillParameter(name="name", required=True)],
        body="Say hello to {name}",
    )

    class FakeClient:
        async def complete(self, messages, **kwargs):
            return f"Hello, {messages[-1]['content'].split()[-1]}"

    tool = SkillTool(manifest, client=FakeClient())
    result = await tool.run(name="EV")
    assert result["skill"] == "hello"
    assert "EV" in result["rendered"]
    assert "Hello, EV" in result["text"]


def test_skill_manager_discovers_built_in_skills(tmp_path, monkeypatch):
    # Create a fake built-in skills directory with one skill.
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "hello_skill").mkdir()
    (skills_dir / "hello_skill" / "SKILL.md").write_text(
        "---\nname: hello_skill\ndescription: A test skill\n---\n# Test\n"
    )

    from ev.config import Settings

    settings = Settings(skills_dir=skills_dir)
    manager = SkillManager(settings=settings)
    catalog = manager.discover()
    assert "hello_skill" in catalog
