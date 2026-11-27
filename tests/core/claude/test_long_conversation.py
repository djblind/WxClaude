import pytest

from wxclaude.core.claude.long_conversation import (
    COMPACT,
    OFF,
    WARN,
    LongAction,
    LongConversationWatch,
)

pytestmark = pytest.mark.unit


def watch_at(tokens: int | None) -> LongConversationWatch:
    watch = LongConversationWatch()
    if tokens is not None:
        watch.record(tokens)
    return watch


def test_nothing_is_done_before_the_first_answer_or_under_the_threshold() -> None:
    assert watch_at(None).after_message(WARN, 100) is LongAction.NONE
    assert watch_at(99_999).after_message(COMPACT, 100) is LongAction.NONE


def test_over_the_threshold_the_choice_decides() -> None:
    assert watch_at(100_000).after_message(OFF, 100) is LongAction.NONE
    assert watch_at(100_000).after_message(WARN, 100) is LongAction.WARN
    assert watch_at(100_000).after_message(COMPACT, 100) is LongAction.COMPACT


def test_the_warning_is_given_once_until_the_conversation_is_short_again() -> None:
    watch = watch_at(150_000)
    assert watch.after_message(WARN, 100) is LongAction.WARN
    watch.record(160_000)
    assert watch.after_message(WARN, 100) is LongAction.NONE
    watch.compacted(30_000)
    assert watch.after_message(WARN, 100) is LongAction.NONE
    watch.record(120_000)
    assert watch.after_message(WARN, 100) is LongAction.WARN


def test_compaction_is_asked_every_time_the_conversation_is_over() -> None:
    watch = watch_at(150_000)
    assert watch.after_message(COMPACT, 100) is LongAction.COMPACT
    assert watch.after_message(COMPACT, 100) is LongAction.COMPACT


def test_another_conversation_starts_unknown() -> None:
    watch = watch_at(150_000)
    watch.after_message(WARN, 100)
    watch.start_conversation()
    assert watch.tokens is None
    watch.record(150_000)
    assert watch.after_message(WARN, 100) is LongAction.WARN
