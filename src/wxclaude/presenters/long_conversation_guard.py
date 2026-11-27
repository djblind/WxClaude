"""What is done when a conversation grew long, once a message is over (``docs/interface.md``,
"Long conversation"). The decision is in ``core/claude/long_conversation.py``; here it is said, or
``/compact`` is sent. Nothing here touches wx."""

from collections.abc import Callable

from wxclaude.core.claude.events import Compacted, ContextSize
from wxclaude.core.claude.long_conversation import (
    COMPACT_COMMAND,
    LongAction,
    LongConversationWatch,
)
from wxclaude.core.config.settings import Settings
from wxclaude.core.numbers import format_tokens
from wxclaude.core.speech.announcements import Announce


class LongConversationGuard:
    """Follows the size of the conversation (``watch``) and acts as the settings say once a message
    is over: ``say`` announces, ``send`` sends a message (False if it could not start)."""

    def __init__(
        self,
        watch: Callable[[], LongConversationWatch],
        settings: Settings,
        say: Callable[..., None],
        send: Callable[[str], bool],
    ) -> None:
        self._watch = watch
        self._settings = settings
        self._say = say
        self._send = send
        self._compacting = False  # the message under way is a compaction: never another one

    def message_started(self, text: str) -> None:
        """A message is sent (by the user or by this guard)."""
        self._compacting = text.strip().lower() == COMPACT_COMMAND

    def observe(self, event: ContextSize | Compacted) -> None:
        """An answer told the size of the conversation, or the CLI compacted it."""
        if isinstance(event, ContextSize):
            self._watch().record(event.tokens)
        else:
            self._watch().compacted(event.post_tokens)

    def message_done(self) -> None:
        """A message ended well: warn, or compact, if the conversation is over the threshold."""
        if self._compacting:
            return
        watch = self._watch()
        action = watch.after_message(
            self._settings.long_conversation, self._settings.long_conversation_thousands
        )
        if action is LongAction.NONE or watch.tokens is None:
            return
        tokens = format_tokens(watch.tokens)
        if action is LongAction.WARN:
            self._say(Announce.LONG_CONVERSATION, tokens=tokens)
            return
        self._say(Announce.LONG_CONVERSATION_COMPACTING, tokens=tokens)
        self._send(COMPACT_COMMAND)
