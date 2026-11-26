"""What the providers of the Agent SDK spent, month by month (``docs/agent-sdk.md``, "Spending").

The API credits of a plan are spent by the messages of a provider whose engine is the Agent SDK,
and an API key cannot ask how much is left. So WxClaude adds the cost of each such message (what the
CLI reports, at list price) to a ledger of its own, ``credits.json`` beside the settings: for each
month (``YYYY-MM``, local time), the dollars of each provider (by its identifier). The dialog of the
gauge shows the spending of the month; the balance itself is on the console of Anthropic.

The file is read again before each addition, so two windows that answer at the same time do not
erase each other's messages.
"""

from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.config.jsonstore import read_json, write_json

FILE_NAME = "credits.json"


def _amount(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return 0.0
    return float(value)


@dataclass(slots=True)
class CreditLedger:
    """The spending of each provider by month. Without ``store`` it stays in memory."""

    months: dict[str, dict[str, float]] = field(default_factory=dict)
    store: Path | None = None
    warning: str = ""  # what went wrong while reading the file, for the user

    @classmethod
    def load(cls, store: Path | None) -> CreditLedger:
        """The ledger in ``store`` (None: an empty one in memory)."""
        ledger = cls(store=store)
        if store is None:
            return ledger
        result = read_json(store)
        ledger.warning = result.warning
        months = None if result.data is None else result.data.get("months")
        if isinstance(months, dict):
            for month, providers in months.items():
                if isinstance(providers, dict):
                    ledger.months[str(month)] = {
                        str(name): _amount(spent) for name, spent in providers.items()
                    }
        return ledger

    def spent(self, provider_id: str, month: str) -> float:
        """The dollars ``provider_id`` spent in ``month`` (``YYYY-MM``)."""
        return self.months.get(month, {}).get(provider_id, 0.0)

    def add(self, provider_id: str, month: str, cost: float) -> None:
        """Count ``cost`` dollars for ``provider_id`` in ``month`` (nothing for no cost)."""
        if cost <= 0:
            return
        providers = self.months.setdefault(month, {})
        providers[provider_id] = providers.get(provider_id, 0.0) + cost

    def save(self) -> None:
        """Write the ledger; raises ``JsonStoreError``. Nothing is written without a store."""
        if self.store is not None:
            write_json(self.store, {"months": dict(sorted(self.months.items()))})


def record_spending(store: Path | None, provider_id: str, month: str, cost: float) -> None:
    """Add ``cost`` to the ledger in ``store``, read again first; raises ``JsonStoreError``."""
    if store is None or cost <= 0:
        return
    ledger = CreditLedger.load(store)
    ledger.add(provider_id, month, cost)
    ledger.save()
