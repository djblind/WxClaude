"""Signing in to another account of Claude with ``claude setup-token`` (a fake console)."""

import queue
import threading

import pytest

from wxclaude.core.claude.account_token import (
    AccountSignIn,
    TokenEnded,
    TokenEvent,
    TokenReceived,
    TokenUrl,
    plain_text,
)
from wxclaude.core.errors import ClaudeLoginError

pytestmark = pytest.mark.unit

TOKEN = "sk-ant-oat01-" + "A1b2_C3d4-" * 8
URL = "https://claude.com/cai/oauth/authorize?code=true&state=secret"


class FakeTerminal:
    """Prints the address, waits for a code, then prints the token and ends."""

    def __init__(self, *, gives_token: bool = True) -> None:
        self.output: queue.Queue[str | None] = queue.Queue()
        self.written: list[str] = []
        self.alive = True
        self.gives_token = gives_token
        self.output.put("\x1b[2J\x1b[?25l✻ Opening the browser…\r\n")
        self.output.put(f"Browser didn't open? Use the url below\r\n\x1b[1m{URL}\x1b[0m\r\n")
        self.output.put("Paste code here if prompted >")

    def read(self, size: int = 4096) -> str:
        chunk = self.output.get(timeout=10)
        if chunk is None:
            raise EOFError
        return chunk

    def write(self, text: str) -> int:
        self.written.append(text)
        if self.gives_token:
            self.output.put(
                f"\r\nYour OAuth token (valid for 1 year):\r\n\x1b[32m{TOKEN}\x1b[0m\r\n"
            )
        else:
            self.output.put("\r\nOAuth error: invalid code\r\n")
        self.end()
        return len(text)

    def isalive(self) -> bool:
        return self.alive

    def terminate(self, force: bool = False) -> bool:
        self.end()
        return True

    def end(self) -> None:
        if self.alive:
            self.alive = False
            self.output.put(None)


class Events:
    def __init__(self) -> None:
        self.events: list[TokenEvent] = []
        self.url = threading.Event()
        self.done = threading.Event()

    def __call__(self, event: TokenEvent) -> None:
        self.events.append(event)
        if isinstance(event, TokenUrl):
            self.url.set()
        if isinstance(event, TokenEnded):
            self.done.set()

    @property
    def ended(self) -> TokenEnded:
        assert self.done.wait(10)
        last = self.events[-1]
        assert isinstance(last, TokenEnded)
        return last


def sign_in(terminal: FakeTerminal) -> tuple[AccountSignIn, list[list[str]]]:
    started: list[list[str]] = []

    def spawn(argv: list[str], env: dict[str, str]) -> FakeTerminal:
        started.append(argv)
        assert not any(name.startswith("ANTHROPIC_") for name in env)
        return terminal

    return AccountSignIn(["claude"], spawn=spawn), started


def test_the_code_given_brings_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost:1234")
    terminal = FakeTerminal()
    login, started = sign_in(terminal)
    events = Events()
    login.start(events)
    assert started == [["claude", "setup-token"]]
    assert events.url.wait(10)
    assert login.is_running
    login.send_code("  the-code#state  ")
    ended = events.ended
    assert terminal.written == ["the-code#state\r"]
    assert TokenUrl(URL) in events.events
    received = [event for event in events.events if isinstance(event, TokenReceived)]
    assert [event.token for event in received] == [TOKEN]
    assert ended.succeeded
    assert TOKEN not in ended.output  # nor in a message
    assert "secret" not in ended.output
    assert TOKEN not in repr(received[0])
    assert not login.is_running


def test_a_refused_code_ends_without_a_token() -> None:
    login, _started = sign_in(FakeTerminal(gives_token=False))
    events = Events()
    login.start(events)
    assert events.url.wait(10)
    login.send_code("wrong")
    ended = events.ended
    assert not ended.succeeded
    assert not ended.cancelled
    assert "invalid code" in ended.output


def test_a_cancelled_sign_in_says_so() -> None:
    login, _started = sign_in(FakeTerminal())
    events = Events()
    login.start(events)
    assert events.url.wait(10)
    with pytest.raises(ClaudeLoginError):
        login.start(Events())  # one at a time
    login.cancel()
    ended = events.ended
    assert ended.cancelled
    assert not ended.succeeded
    with pytest.raises(ClaudeLoginError):
        login.send_code("late")
    login.cancel()  # nothing runs: nothing happens


def test_the_control_sequences_are_removed() -> None:
    assert plain_text("\x1b[1mbold\x1b[0m\r\n\x1b]0;title\x07x") == "bold\nx"
