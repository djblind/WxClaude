"""Adding each finished message to the statistics of the workspace, and to the spending of the
API credits when its provider uses the Agent SDK.

The time of a message is the one the CLI reports minus the time the user took to answer the
permission questions of that message, which the CLI counts in it (``docs/claude-cli.md``,
"The stream"). The presenter that follows the message tells when a question is open
(``waiting``) and when the message ends (``record``).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from wxclaude.core.claude.events import TurnResult
from wxclaude.core.config.credit_ledger import record_spending
from wxclaude.core.config.workspace_stats import CountedMessage, WorkspaceStats
from wxclaude.core.errors import JsonStoreError
from wxclaude.i18n import _


class StatsRecorder:
    """Records the finished messages in the statistics of the current workspace.

    ``stats`` gives them (None without a workspace); ``credits`` gives the ledger of the spending
    of the API credits (``credit_ledger.py``; None: not kept). ``report`` is told when one of them
    cannot be saved, once each: the next messages are still counted, and a message at each answer
    would only be a burden.
    """

    def __init__(
        self,
        stats: Callable[[], WorkspaceStats | None],
        report: Callable[[str], None],
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = datetime.now,
        *,
        credits: Callable[[], Path | None] = lambda: None,
    ) -> None:
        self._stats = stats
        self._report = report
        self._clock = clock
        self._now = now
        self._credits = credits
        self._waited = 0.0  # seconds spent on the permission questions of this message
        self._credit_provider = ""  # the provider of the message when it spends the API credits
        self._reported = False
        self._credits_reported = False

    def start_message(self, credit_provider: str = "") -> None:
        """A message starts: no question was open yet. ``credit_provider``: the identifier of its
        provider when it spends the API credits (Agent SDK), else ''."""
        self._waited = 0.0
        self._credit_provider = credit_provider

    @contextmanager
    def waiting(self) -> Iterator[None]:
        """A permission question is open: the time it stays open is not time of work."""
        started = self._clock()
        try:
            yield
        finally:
            self._waited += self._clock() - started

    def record(
        self, result: TurnResult, *, conversation_id: str, model: str, cost: float | None
    ) -> None:
        """Count the message that ended with ``result`` (``cost`` is its own cost, if known), and
        its cost in the spending of the API credits when its provider spends them."""
        if self._credit_provider and cost:
            self._record_spending(self._credit_provider, cost)
        stats = self._stats()
        if stats is None:
            return
        activity = max(0, (result.duration_ms or 0) - round(self._waited * 1000))
        stats.record_message(
            CountedMessage(
                conversation_id,
                result.usage,
                activity,
                cost,
                model,
                self._now().date().isoformat(),
            )
        )
        try:
            stats.save()
        except JsonStoreError as error:
            if not self._reported:
                self._reported = True
                self._report(
                    _("The statistics of the workspace could not be saved.\n{error}").format(
                        error=error
                    )
                )

    def _record_spending(self, provider_id: str, cost: float) -> None:
        try:
            record_spending(self._credits(), provider_id, self._now().strftime("%Y-%m"), cost)
        except JsonStoreError as error:
            if not self._credits_reported:
                self._credits_reported = True
                self._report(
                    _("The spending of the API credits could not be saved.\n{error}").format(
                        error=error
                    )
                )
