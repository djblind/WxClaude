"""The Activity field: what the run presenter shows of what Claude and its subagents do."""

from pathlib import Path

import pytest
from test_run_presenter_security import presenter_for

from wxclaude.core.claude.events import AssistantText, ToolUsed
from wxclaude.core.config.agents import Agent

pytestmark = pytest.mark.unit

AGENT = Agent(model="haiku", effort="low", permission_mode="manual")


def test_what_claude_does_goes_to_the_activity_and_a_new_message_clears_it(
    tmp_path: Path,
) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("one", AGENT)
    presenter.on_event(ToolUsed("t1", "Read", {"file_path": "a.txt"}))
    presenter.on_event(AssistantText("Read.", "m"))
    assert view.activity == ["Claude: Read a.txt", "Claude: Read."]
    presenter.start("two", AGENT)
    assert view.activity == []


def test_the_text_of_a_subagent_is_only_in_the_activity(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("one", AGENT)
    presenter.on_event(ToolUsed("a1", "Agent", {"subagent_type": "chercheur"}))
    presenter.on_event(AssistantText("Found 3 files.", "claude-haiku-5-5", parent="a1"))
    assert view.activity[-1] == "Subagent chercheur: Found 3 files."
    assert [message.text for message in view.messages] == ["one"]
