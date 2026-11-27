"""Going on in a new conversation after a pause (``docs/interface.md``, "Fresh start after a
pause").

Claude keeps what it already read in a cache for one hour at most (the subscription uses the cache
of one hour: ``ephemeral_1h_input_tokens``, ``docs/claude-cli.md``). A long conversation taken up
again after that is written to the cache again whole, then read again at every message: it costs
much more than a new conversation. The new conversation gets, before the message of the user, the
last exchanges of the old one (made here from the session file: no token is spent to make it) and
the place of the old session file, so that Claude knows what the work was and goes on with it.
"""

from datetime import UTC, datetime, timedelta

from wxclaude.core.conversation.messages import Message, Role
from wxclaude.i18n import _

ASK = "ask"
ALWAYS = "always"
NEVER = "never"
CHOICES = (ASK, ALWAYS, NEVER)
DEFAULT_CHOICE = ASK
PAUSE = timedelta(hours=1)  # the life of the cache
_BUDGET = 40_000  # characters of exchanges given to the new conversation (about 10 000 tokens)
_LONGEST_MESSAGE = 6_000  # characters kept of one message (its start)


def conversation_size(messages: list[Message]) -> int | None:
    """What the last answer read (sent, read from and written to the cache), None if unknown."""
    for message in reversed(messages):
        usage = message.usage
        if message.role is Role.ASSISTANT and usage is not None:
            size = usage.input_tokens + usage.cache_read_input_tokens
            size += usage.cache_creation_input_tokens
            if size:
                return size
    return None


def _moment(stamp: str) -> datetime | None:
    """An ISO 8601 time of the session file (``2026-11-27T17:34:52.123Z``), None if unreadable."""
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def worth_fresh_start(
    messages: list[Message], ended: str, threshold_tokens: int, now: datetime
) -> bool:
    """Is the conversation long (``threshold_tokens`` or more) and was its last entry ``ended``
    more than an hour before ``now`` (aware)? Then the cache is gone and going on costs much."""
    size = conversation_size(messages)
    last = _moment(ended) if ended else None
    if size is None or size < threshold_tokens or last is None:
        return False
    return now - last > PAUSE


def _exchange(message: Message) -> str:
    """One message of the old conversation, as the new one reads it."""
    text = message.text.strip()
    if len(text) > _LONGEST_MESSAGE:
        text = text[:_LONGEST_MESSAGE] + " […]"
    if message.role is Role.USER:
        return _("[User] {text}").format(text=text)
    return _("[Claude] {text}").format(text=text)


def last_exchanges(messages: list[Message], budget: int = _BUDGET) -> list[str]:
    """The last prompts and answers that fit in ``budget`` characters, oldest first (never less
    than the last one). Hidden messages and empty ones are left out."""
    kept: list[str] = []
    used = 0
    for message in reversed(messages):
        if message.hidden or not message.text.strip():
            continue
        exchange = _exchange(message)
        if kept and used + len(exchange) > budget:
            break
        kept.append(exchange)
        used += len(exchange)
    return list(reversed(kept))


def handoff_prompt(old_name: str, session_file: str, messages: list[Message], text: str) -> str:
    """The first message of the new conversation: where it comes from, the last exchanges of the
    old one, then what the user just asked."""
    exchanges = "\n\n".join(last_exchanges(messages))
    return _(
        'This conversation goes on with the conversation "{name}", which had grown too long to be '
        "taken up again after a pause. Here are its last exchanges, oldest first:\n\n"
        "{exchanges}\n\n"
        "If you need more, the whole old conversation is in {file} (a JSONL session file of "
        "Claude Code): read only the part you need. Go on with the work where it was.\n\n"
        "New message of the user:\n{text}"
    ).format(name=old_name, exchanges=exchanges, file=session_file, text=text)


def continued_name(name: str) -> str:
    """The name of the new conversation."""
    return _("{name} (continued)").format(name=name) if name else _("Continued conversation")
