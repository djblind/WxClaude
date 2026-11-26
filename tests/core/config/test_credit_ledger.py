"""The ledger of what the Agent SDK providers spent, month by month."""

import json
from pathlib import Path

import pytest

from wxclaude.core.config.credit_ledger import CreditLedger, record_spending

pytestmark = pytest.mark.unit


def test_spending_is_added_by_provider_and_month(tmp_path: Path) -> None:
    store = tmp_path / "credits.json"
    record_spending(store, "api", "2026-11", 0.25)
    record_spending(store, "api", "2026-11", 0.5)
    record_spending(store, "other", "2026-11", 1.0)
    record_spending(store, "api", "2026-12", 2.0)
    ledger = CreditLedger.load(store)
    assert ledger.spent("api", "2026-11") == pytest.approx(0.75)
    assert ledger.spent("other", "2026-11") == 1.0
    assert ledger.spent("api", "2026-12") == 2.0
    assert ledger.spent("api", "2027-01") == 0.0


def test_the_file_is_read_again_before_each_addition(tmp_path: Path) -> None:
    """Two windows: what the other one wrote is kept."""
    store = tmp_path / "credits.json"
    record_spending(store, "api", "2026-11", 1.0)
    other = CreditLedger.load(store)
    other.add("api", "2026-11", 2.0)
    other.save()
    record_spending(store, "api", "2026-11", 0.5)
    assert CreditLedger.load(store).spent("api", "2026-11") == pytest.approx(3.5)


def test_nothing_is_written_without_a_cost_or_a_file(tmp_path: Path) -> None:
    store = tmp_path / "credits.json"
    record_spending(store, "api", "2026-11", 0.0)
    record_spending(None, "api", "2026-11", 1.0)
    assert not store.exists()


def test_wrong_values_in_the_file_count_as_nothing(tmp_path: Path) -> None:
    store = tmp_path / "credits.json"
    data = {"months": {"2026-11": {"api": "lots", "b": -2, "c": True, "d": 1.5}, "x": 3}}
    store.write_text(json.dumps(data), encoding="utf-8")
    ledger = CreditLedger.load(store)
    assert [ledger.spent(name, "2026-11") for name in ("api", "b", "c", "d")] == [0, 0, 0, 1.5]
    assert ledger.warning == ""


def test_a_damaged_file_is_set_aside_and_said(tmp_path: Path) -> None:
    store = tmp_path / "credits.json"
    store.write_text("{not json", encoding="utf-8")
    ledger = CreditLedger.load(store)
    assert ledger.months == {}
    assert "credits.json" in ledger.warning
