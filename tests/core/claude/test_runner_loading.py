"""A message to a provider whose models WxClaude loads: the model first, then the CLI (a fake
loading method and the fake CLI)."""

import sys
import threading
from pathlib import Path

import pytest

from wxclaude.core.claude.events import ModelLoading, RunEvent, SessionInit, TurnEnded
from wxclaude.core.claude.launch import ProviderLaunch, provider_settings
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.model_loading import LOADING, LoadingMethod, Report
from wxclaude.core.config.providers import KEY_NONE, Provider
from wxclaude.core.errors import ModelLoadError, RunnerError

pytestmark = pytest.mark.unit

FAKE = Path(__file__).resolve().parents[2] / "fakes" / "fake_claude.py"
LOCAL = Provider(
    id="lm",
    name="LM Studio",
    base_url="http://localhost:1234",
    key_source=KEY_NONE,
    tiers=["small", "big"],
    env={"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "131072"},
    loading_method="lmstudio",
)


class Collector:
    def __init__(self) -> None:
        self.events: list[RunEvent] = []
        self.done = threading.Event()

    def __call__(self, event: RunEvent) -> None:
        self.events.append(event)
        if isinstance(event, TurnEnded):
            self.done.set()

    def wait(self) -> TurnEnded:
        assert self.done.wait(30), "the run did not end"
        last = self.events[-1]
        assert isinstance(last, TurnEnded)
        return last


class FakeLoading(LoadingMethod):
    id = "fake"
    label = "Fake"

    def __init__(self, failure: str = "") -> None:
        self.asked: list[tuple[str, str, int | None]] = []
        self.failure = failure
        self.release = threading.Event()
        self.release.set()
        self.started = threading.Event()

    def prepare(
        self, base_url: str, model: str, context_length: int | None, report: Report
    ) -> None:
        self.asked.append((base_url, model, context_length))
        report(LOADING, [model])
        self.started.set()
        self.release.wait(30)
        if self.failure:
            raise ModelLoadError(self.failure)


@pytest.fixture
def loading(monkeypatch: pytest.MonkeyPatch) -> FakeLoading:
    fake = FakeLoading()
    monkeypatch.setattr("wxclaude.core.claude.runner.loading_method", lambda identifier: fake)
    return fake


def _request(tmp_path: Path, provider: Provider = LOCAL) -> RunRequest:
    agent = Agent(model="big", effort="low", permission_mode="manual", provider=provider.id)
    return RunRequest(
        "Hello",
        agent,
        "11111111-1111-4111-8111-111111111111",
        False,
        tmp_path,
        provider=ProviderLaunch(provider, scrub=False),
    )


def _runner() -> ClaudeRunner:
    return ClaudeRunner([sys.executable, str(FAKE)])


def test_the_model_is_loaded_before_the_cli_starts(tmp_path: Path, loading: FakeLoading) -> None:
    collector = Collector()
    _runner().start(_request(tmp_path), collector)
    ended = collector.wait()
    assert loading.asked == [("http://localhost:1234", "big", 131072)]
    assert collector.events[0] == ModelLoading(LOADING, ("big",))
    assert any(isinstance(event, SessionInit) for event in collector.events)
    assert ended.exit_code == 0


def test_a_model_that_cannot_be_loaded_ends_the_message(
    tmp_path: Path, loading: FakeLoading
) -> None:
    loading.failure = "LM Studio has no model big."
    collector = Collector()
    runner = _runner()
    runner.start(_request(tmp_path), collector)
    ended = collector.wait()
    assert ended.stderr == "LM Studio has no model big."
    assert not ended.interrupted
    assert not any(isinstance(event, SessionInit) for event in collector.events)
    assert not runner.is_running


def test_an_interruption_while_loading_does_not_start_the_cli(
    tmp_path: Path, loading: FakeLoading
) -> None:
    loading.release.clear()
    collector = Collector()
    runner = _runner()
    runner.start(_request(tmp_path), collector)
    assert loading.started.wait(30)
    assert runner.is_running
    with pytest.raises(RunnerError):
        runner.start(_request(tmp_path), Collector())  # one message at a time, loading included
    runner.interrupt()
    loading.release.set()
    ended = collector.wait()
    assert ended.interrupted
    assert not any(isinstance(event, SessionInit) for event in collector.events)


def test_a_provider_without_a_method_loads_nothing(tmp_path: Path, loading: FakeLoading) -> None:
    plain = Provider(id="p", name="P", base_url="http://x", key_source=KEY_NONE, tiers=["big"])
    collector = Collector()
    _runner().start(_request(tmp_path, plain), collector)
    collector.wait()
    assert loading.asked == []


def test_the_aliases_of_a_provider_that_loads_go_to_the_model_of_the_message() -> None:
    env = provider_settings(ProviderLaunch(LOCAL), "big")["env"]
    assert isinstance(env, dict)
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "big"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "big"
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "big"
    plain = provider_settings(ProviderLaunch(Provider(id="p", name="P", tiers=["a", "b"])), "b")
    assert plain["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "a"  # type: ignore[index]
