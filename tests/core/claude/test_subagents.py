import json
from pathlib import Path

import pytest

from wxclaude.core.claude.permission_channel import StdioChannel
from wxclaude.core.claude.runner import RunRequest, build_arguments
from wxclaude.core.claude.subagents import SUBAGENTS, subagents_argument
from wxclaude.core.config.agents import Agent

pytestmark = pytest.mark.unit

AGENT = Agent(model="haiku", effort="low", permission_mode="manual")


def test_the_reader_only_reads_on_haiku_and_the_worker_is_on_sonnet() -> None:
    assert SUBAGENTS["lecteur"]["model"] == "haiku"
    assert SUBAGENTS["lecteur"]["tools"] == ["Read", "Grep", "Glob", "Bash"]
    assert SUBAGENTS["executant"]["model"] == "sonnet"
    assert "tools" not in SUBAGENTS["executant"]  # every tool, as the conversation


def test_the_subagents_go_to_the_cli_as_one_json_argument(tmp_path: Path) -> None:
    assert subagents_argument({}) == []
    request = RunRequest("Hi", AGENT, "s", False, tmp_path, subagents=SUBAGENTS)
    arguments = build_arguments(request, StdioChannel())
    given = arguments[arguments.index("--agents") + 1]
    assert json.loads(given) == SUBAGENTS
    plain = RunRequest("Hi", AGENT, "s", False, tmp_path)
    assert "--agents" not in build_arguments(plain, StdioChannel())
