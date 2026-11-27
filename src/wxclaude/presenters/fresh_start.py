"""Before a message is sent: a long conversation left for more than an hour goes on in a new
conversation, which gets the last exchanges of the old one (``core/conversation/handoff.py``,
``docs/interface.md``, "Fresh start after a pause"). Owned by ``ConversationPresenter``. Nothing
here touches wx."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from wxclaude.core.conversation.handoff import (
    ALWAYS,
    NEVER,
    continued_name,
    handoff_prompt,
    worth_fresh_start,
)
from wxclaude.core.errors import SessionReadError
from wxclaude.i18n import _
from wxclaude.presenters.shared import Shared


class FreshStartView(Protocol):
    """What is asked of the window."""

    def propose(self, title: str, message: str) -> bool:
        """Ask a Yes / No question, Yes by default; True for Yes."""
        ...

    def clear_messages(self) -> None:
        """Empty the conversation view."""
        ...


@dataclass(frozen=True, slots=True)
class FreshStartLinks:
    """The current conversation (its identifier and name) and how to start a new one by name."""

    conversation_id: Callable[[], str]
    name: Callable[[], str]
    start_new: Callable[[str], None]
    now: Callable[[], datetime] = lambda: datetime.now(UTC)


class FreshStart:
    """Decides, before a message, whether it goes on in a new conversation, and makes it so."""

    def __init__(self, view: FreshStartView, shared: Shared, links: FreshStartLinks) -> None:
        self._view = view
        self._settings = shared.settings
        self._files = shared.files
        self._links = links

    def text_to_send(self, text: str) -> str:
        """``text`` as it is, or, when the conversation goes on in a new one (asked, or always as
        the settings say), the first message of the new conversation, which is then current."""
        choice = self._settings.fresh_start
        if choice == NEVER:
            return text
        path = self._files.find_session(self._links.conversation_id())
        if path is None:
            return text
        try:
            session = self._files.read_session(path)
        except SessionReadError:
            return text  # the message goes on in the conversation; the view tells about the file
        threshold = self._settings.long_conversation_thousands * 1000
        if not worth_fresh_start(session.messages, session.ended, threshold, self._links.now()):
            return text
        if choice != ALWAYS and not self._view.propose(
            _("Long conversation after a pause"),
            _(
                "This conversation is long and was left more than an hour ago: taking it up again "
                "costs much of the quota. Go on in a new conversation, which gets its last "
                "exchanges and goes on with the work?"
            ),
        ):
            return text
        old_name = self._links.name()
        self._view.clear_messages()
        self._links.start_new(continued_name(old_name))
        return handoff_prompt(old_name, str(path), session.messages, text)
