"""A conversation that grew long: say it, or compact it (``docs/interface.md``, "Long
conversation").

Claude reads the whole conversation again for every message it answers, so a long conversation
spends most of the subscription on reading it again. The size of what Claude read is the one of the
last answer of the main conversation (``ContextSize``, from the ``usage`` of the ``assistant``
lines: the tokens sent plus the ones read from and written to the cache). When a message ends with
the conversation over the threshold of the settings, one of three things is done:

- ``off``: nothing;
- ``warn``: say it once, until the conversation goes under the threshold again (a compaction);
- ``compact``: send ``/compact`` at once, which replaces the conversation by a summary.
"""

import enum

OFF = "off"
WARN = "warn"
COMPACT = "compact"
CHOICES = (OFF, WARN, COMPACT)
DEFAULT_CHOICE = WARN
THRESHOLD_THOUSANDS = range(20, 1001)  # the threshold of the settings, in thousands of tokens
DEFAULT_THRESHOLD_THOUSANDS = 100
COMPACT_COMMAND = "/compact"  # the command of the CLI, checked through ``-p`` (``claude-cli.md``)


class LongAction(enum.Enum):
    """What to do once a message is over."""

    NONE = "none"
    WARN = "warn"
    COMPACT = "compact"


class LongConversationWatch:
    """Follows the size of the current conversation and tells what to do after each message."""

    def __init__(self) -> None:
        self.tokens: int | None = None  # the size of the conversation, None until an answer
        self._warned = False

    def start_conversation(self) -> None:
        """Another conversation is current: its size is not known yet."""
        self.tokens = None
        self._warned = False

    def record(self, tokens: int) -> None:
        """An answer of the main conversation read ``tokens``."""
        self.tokens = tokens

    def compacted(self, post_tokens: int | None) -> None:
        """The conversation was compacted: it is now its summary (the next answer tells more)."""
        self.tokens = post_tokens
        self._warned = False

    def after_message(self, choice: str, threshold_thousands: int) -> LongAction:
        """What ``choice`` (``CHOICES``) asks once a message is over, for the threshold given in
        thousands of tokens. A warning is given once, until the size goes under the threshold."""
        if self.tokens is None or self.tokens < threshold_thousands * 1000:
            self._warned = False
            return LongAction.NONE
        if choice == COMPACT:
            return LongAction.COMPACT
        if choice != WARN or self._warned:
            return LongAction.NONE
        self._warned = True
        return LongAction.WARN
