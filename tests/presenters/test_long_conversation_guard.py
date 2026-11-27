"""What the run presenter does when the conversation grew long, once a message is over."""

from pathlib import Path

import pytest
from test_run_presenter_security import presenter_for

from wxclaude.core.claude.events import Compacted, ContextSize, TurnEnded, TurnResult
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.run_presenter import RunPresenter

pytestmark = pytest.mark.unit

AGENT = Agent(model="haiku", effort="low", permission_mode="manual")


def settings(choice: str) -> Settings:
    loaded = Settings.load(None)
    loaded.long_conversation = choice
    loaded.long_conversation_thousands = 100
    return loaded


def answer(presenter: RunPresenter, tokens: int) -> None:
    """A message answered well after reading ``tokens``."""
    presenter.on_event(ContextSize(tokens))
    presenter.on_event(TurnResult(False, "success", "ok", None, 10, None, 1))
    presenter.on_event(TurnEnded(0, False, "", []))


def test_a_long_conversation_is_said_once(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None, settings=settings("warn"))
    presenter.start("one", AGENT)
    answer(presenter, 150_000)
    presenter.start("two", AGENT)
    answer(presenter, 160_000)
    assert view.announces().count(Announce.LONG_CONVERSATION) == 1
    assert (Announce.LONG_CONVERSATION, {"name": "Claude", "tokens": "150000"}) in view.said
    assert [request.prompt for request in runner.requests] == ["one", "two"]


def test_a_short_conversation_says_nothing(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None, settings=settings("warn"))
    presenter.start("one", AGENT)
    answer(presenter, 50_000)
    assert Announce.LONG_CONVERSATION not in view.announces()


def test_the_automatic_mode_sends_compact_once(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None, settings=settings("compact"))
    presenter.start("one", AGENT)
    answer(presenter, 150_000)
    assert [request.prompt for request in runner.requests] == ["one", "/compact"]
    assert Announce.LONG_CONVERSATION_COMPACTING in view.announces()
    presenter.on_event(Compacted("manual", 150_000, 20_000))
    presenter.on_event(TurnEnded(0, False, "", []))  # the end of /compact: nothing more
    assert [request.prompt for request in runner.requests] == ["one", "/compact"]


def test_a_failed_compaction_is_not_sent_again_in_a_loop(tmp_path: Path) -> None:
    presenter, runner, _view = presenter_for(tmp_path, None, settings=settings("compact"))
    presenter.start("one", AGENT)
    answer(presenter, 150_000)
    answer(presenter, 150_000)  # /compact ended without compacting
    assert [request.prompt for request in runner.requests] == ["one", "/compact"]


def test_off_does_nothing(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None, settings=settings("off"))
    presenter.start("one", AGENT)
    answer(presenter, 500_000)
    assert [request.prompt for request in runner.requests] == ["one"]
    assert Announce.LONG_CONVERSATION not in view.announces()
