from datetime import UTC, datetime

import pytest

from wxclaude.core.conversation.handoff import (
    continued_name,
    conversation_size,
    handoff_prompt,
    last_exchanges,
    worth_fresh_start,
)
from wxclaude.core.conversation.messages import Message, Role, Usage

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)


def answer(text: str, size: int = 0) -> Message:
    return Message("a", Role.ASSISTANT, text, usage=Usage(2, 50, 1000, size - 1002))


def prompt(text: str) -> Message:
    return Message("u", Role.USER, text)


def test_the_size_is_the_one_of_the_last_answer() -> None:
    messages = [prompt("a"), answer("b", 50_000), prompt("c"), answer("d", 180_000), prompt("e")]
    assert conversation_size(messages) == 180_000
    assert conversation_size([prompt("a")]) is None


def test_only_a_long_conversation_left_for_more_than_an_hour_is_worth_a_fresh_start() -> None:
    long = [prompt("a"), answer("b", 150_000)]
    assert worth_fresh_start(long, "2026-11-28T08:30:00.000Z", 100_000, NOW)
    assert not worth_fresh_start(long, "2026-11-28T09:30:00.000Z", 100_000, NOW)  # cache alive
    short = [prompt("a"), answer("b", 60_000)]
    assert not worth_fresh_start(short, "2026-11-27T08:30:00.000Z", 100_000, NOW)
    assert not worth_fresh_start(long, "", 100_000, NOW)
    assert not worth_fresh_start(long, "yesterday", 100_000, NOW)


def test_the_last_exchanges_fit_the_budget_oldest_first_without_hidden_ones() -> None:
    hidden = Message("h", Role.USER, "noise", hidden=True)
    messages = [prompt("old " * 100), answer("one"), hidden, prompt("two"), answer("three")]
    assert last_exchanges(messages, budget=30) == ["[User] two", "[Claude] three"]
    assert last_exchanges([answer("x" * 100)], budget=10) == ["[Claude] " + "x" * 100]


def test_a_very_long_message_keeps_its_start() -> None:
    (exchange,) = last_exchanges([answer("y" * 7000)])
    assert exchange == "[Claude] " + "y" * 6000 + " […]"


def test_the_first_message_names_the_old_conversation_its_file_and_the_new_request() -> None:
    text = handoff_prompt("Fix", "C:/s.jsonl", [prompt("Translate"), answer("Done")], "Go on")
    assert text.startswith('This conversation goes on with the conversation "Fix"')
    assert "[User] Translate\n\n[Claude] Done" in text
    assert "C:/s.jsonl" in text
    assert text.endswith("New message of the user:\nGo on")
    assert continued_name("Fix") == "Fix (continued)"
    assert continued_name("") == "Continued conversation"
