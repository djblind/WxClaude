"""Before a message: a long conversation left for more than an hour goes on in a new one."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.settings import Settings
from wxclaude.core.conversation.messages import Message, Role, Usage
from wxclaude.presenters.fresh_start import FreshStart, FreshStartLinks
from wxclaude.presenters.shared import Shared

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)


class FakeView:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[str] = []
        self.cleared = 0

    def propose(self, title: str, message: str) -> bool:
        self.asked.append(title)
        return self.answer

    def clear_messages(self) -> None:
        self.cleared += 1


def setup(
    tmp_path: Path, choice: str, size: int, ended: str, answer: bool = True
) -> tuple[FreshStart, FakeView, list[str]]:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "c1", "Translate the file")
    session = files.contents[Path("c1.jsonl")]
    session.messages.append(
        Message("a", Role.ASSISTANT, "Done.", usage=Usage(2, 10, 1000, size - 1002))
    )
    session.ended = ended
    settings = Settings.load(None)
    settings.fresh_start = choice
    view = FakeView(answer)
    started: list[str] = []
    links = FreshStartLinks(lambda: "c1", lambda: "Fix", started.append, now=lambda: NOW)
    return FreshStart(view, Shared(settings, UsageTracker(), files), links), view, started


OLD = "2026-11-28T07:00:00.000Z"  # three hours before NOW


def test_yes_goes_on_in_a_new_conversation_with_the_last_exchanges(tmp_path: Path) -> None:
    fresh, view, started = setup(tmp_path, "ask", 150_000, OLD)
    text = fresh.text_to_send("Go on")
    assert view.asked == ["Long conversation after a pause"]
    assert started == ["Fix (continued)"]
    assert view.cleared == 1
    assert "[User] Translate the file\n\n[Claude] Done." in text
    assert text.endswith("Go on")


def test_no_keeps_the_conversation(tmp_path: Path) -> None:
    fresh, _view, started = setup(tmp_path, "ask", 150_000, OLD, answer=False)
    assert fresh.text_to_send("Go on") == "Go on"
    assert started == []


def test_always_asks_nothing_and_never_does_nothing(tmp_path: Path) -> None:
    fresh, view, started = setup(tmp_path, "always", 150_000, OLD)
    assert fresh.text_to_send("Go on") != "Go on"
    assert (view.asked, started) == ([], ["Fix (continued)"])
    fresh, view, started = setup(tmp_path, "never", 150_000, OLD)
    assert fresh.text_to_send("Go on") == "Go on"
    assert (view.asked, started) == ([], [])


def test_a_short_or_recent_conversation_is_left_alone(tmp_path: Path) -> None:
    fresh, view, _started = setup(tmp_path, "ask", 50_000, OLD)
    assert fresh.text_to_send("Go on") == "Go on"
    fresh, view, _started = setup(tmp_path, "ask", 150_000, "2026-11-28T09:30:00.000Z")
    assert fresh.text_to_send("Go on") == "Go on"
    assert view.asked == []
