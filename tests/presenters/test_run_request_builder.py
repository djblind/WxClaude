from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.presenters.run_presenter import RunLinks
from wxclaude.presenters.run_request_builder import RunRequestBuilder
from wxclaude.presenters.shared import Shared

pytestmark = pytest.mark.unit

AGENT = Agent(model="haiku", effort="low", permission_mode="acceptEdits")


def builder_for(workspace: Path | None, files: FakeClaudeFiles) -> RunRequestBuilder:
    shared = Shared(Settings.load(None), UsageTracker(), files, None, None, None)
    links = RunLinks(
        workspace=lambda: workspace,
        conversation_id=lambda: "c1",
        conversation_name=lambda: "Fix",
        fork_from=lambda: "",
        is_closing=lambda: False,
        state_changed=lambda: None,
    )
    return RunRequestBuilder(shared, links)


def test_no_workspace_gives_no_request() -> None:
    assert builder_for(None, FakeClaudeFiles()).build("hello", AGENT) is None


def test_the_first_message_creates_the_session_and_the_next_ones_resume_it(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    builder = builder_for(tmp_path, files)
    first = builder.build("hello", AGENT)
    assert first is not None
    assert (first.prompt, first.session_id, first.resume, first.cwd, first.name) == (
        "hello",
        "c1",
        False,
        tmp_path,
        "Fix",
    )
    files.add_session(tmp_path, "c1", "hello")
    again = builder.build("more", AGENT)
    assert again is not None
    assert again.resume


def test_a_trusted_folder_keeps_the_mode_of_the_agent(tmp_path: Path) -> None:
    builder = builder_for(tmp_path, FakeClaudeFiles())
    assert not builder.restricted
    assert builder.mode_sent(AGENT) == "acceptEdits"


def test_the_subagents_of_wxclaude_are_given_unless_the_settings_say_no(tmp_path: Path) -> None:
    builder = builder_for(tmp_path, FakeClaudeFiles())
    request = builder.build("hello", AGENT)
    assert request is not None
    assert set(request.subagents) == {"lecteur", "executant"}
    builder._settings.wxclaude_subagents = False
    request = builder.build("hello", AGENT)
    assert request is not None
    assert request.subagents == {}
