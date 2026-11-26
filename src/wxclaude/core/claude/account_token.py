"""Signing in to another account of a Claude plan: ``claude setup-token`` (``docs/providers.md``,
"Accounts of Claude").

The command gives a token that lasts a year and stands for the account the user allowed in the
browser; WxClaude keeps it as the key of a provider whose engine is *Claude account* and gives it to
the CLI as ``CLAUDE_CODE_OAUTH_TOKEN``. The command needs a terminal: through a pipe it prints
nothing (measured 2026-11-26, CLI 2.1.321). So it runs in an invisible pseudo-console (ConPTY,
through ``pywinpty``). It opens the browser by itself, prints the address of the sign-in page (for a
browser that did not open, or to use another one), then waits for the code that the page of Claude
shows once the user has allowed it ("Paste code here if prompted"). Given that code it prints the
token and ends. The token is never written to a file or to the log here. This module never imports
``wx``.
"""

import os
import re
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from wxclaude.core.claude.runner import find_claude
from wxclaude.core.errors import ClaudeLoginError, ClaudeNotFoundError

_URL = re.compile(r"https://\S+")
_TOKEN = re.compile(r"sk-ant-oat\d+-[A-Za-z0-9_\-]{20,}")
_ESCAPE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Z]"
)
_QUERY = re.compile(r"\?\S*")
_COLUMNS = 1000  # wide enough that the address and the token are never cut by the console
_ROWS = 50
_END_WAIT_SECONDS = 10  # once the token is there, the command ends by itself
#: The variables of WxClaude that are not passed on: they could choose another way to reach Claude.
_INHERITED_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_", "CLAUDE_CODE_OAUTH_TOKEN")


@dataclass(frozen=True, slots=True)
class TokenUrl:
    """The address of the sign-in page that the command printed."""

    url: str


@dataclass(frozen=True, slots=True)
class TokenReceived:
    """The token of the account. It is not in the ``repr``."""

    token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class TokenEnded:
    """The command ended. ``output`` is what it printed, without the address details and without
    the token (for an error message)."""

    succeeded: bool
    cancelled: bool
    output: str


TokenEvent = TokenUrl | TokenReceived | TokenEnded


class Terminal(Protocol):
    """What is used of a process in a pseudo-console (``winpty.PtyProcess``; a fake in tests)."""

    def read(self, size: int = ...) -> str: ...

    def write(self, text: str) -> int: ...

    def isalive(self) -> bool: ...

    def terminate(self, force: bool = ...) -> bool: ...


#: Starts ``argv`` in a pseudo-console with ``env``.
type Spawn = Callable[[list[str], dict[str, str]], Terminal]


def _spawn_pty(argv: list[str], env: dict[str, str]) -> Terminal:
    try:
        from winpty import PtyProcess  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError as error:
        raise ClaudeLoginError(
            "The pseudo-console (pywinpty) is not installed: the sign-in cannot run."
        ) from error
    try:
        process: Terminal = PtyProcess.spawn(argv, env=env, dimensions=(_ROWS, _COLUMNS))
    except OSError as error:
        raise ClaudeLoginError(f"Cannot start {argv[0]}: {error}") from error
    return process


def plain_text(raw: str) -> str:
    """The text of the console without its control sequences."""
    return _ESCAPE.sub("", raw).replace("\r", "")


def _shown(text: str) -> str:
    """``text`` without the token and the details of the addresses, for a message."""
    return _QUERY.sub("", _TOKEN.sub("***", text)).strip()


class AccountSignIn:
    """One sign-in at a time. ``command`` replaces the ``claude`` executable and ``spawn`` the
    pseudo-console (tests)."""

    def __init__(
        self,
        command: Sequence[str] | None = None,
        claude_path: str = "",
        spawn: Spawn = _spawn_pty,
    ) -> None:
        self._command = list(command) if command is not None else None
        self.claude_path = claude_path
        self._spawn = spawn
        self._terminal: Terminal | None = None
        self._cancelled = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._terminal is not None

    def start(self, on_event: Callable[[TokenEvent], None]) -> None:
        """Start ``claude setup-token``; ``on_event`` is called from a worker thread. Raises
        ``ClaudeLoginError`` if it cannot be started or if a sign-in already runs."""
        try:
            command = self._command if self._command is not None else find_claude(self.claude_path)
        except ClaudeNotFoundError as error:
            raise ClaudeLoginError(str(error)) from error
        env = {
            name: value
            for name, value in os.environ.items()
            if not name.upper().startswith(_INHERITED_PREFIXES)
        }
        with self._lock:
            if self._terminal is not None:
                raise ClaudeLoginError("A sign-in is already running.")
            terminal = self._spawn([*command, "setup-token"], env)
            self._terminal = terminal
            self._cancelled = False
        threading.Thread(target=self._watch, args=(terminal, on_event), daemon=True).start()

    def send_code(self, code: str) -> None:
        """Give the command the code that the page of Claude shows. Raises ``ClaudeLoginError``
        if no sign-in runs."""
        with self._lock:
            terminal = self._terminal
        if terminal is None:
            raise ClaudeLoginError("No sign-in is running.")
        try:
            terminal.write(code.strip() + "\r")
        except OSError as error:
            raise ClaudeLoginError(str(error)) from error

    def cancel(self) -> None:
        """End the running sign-in; its ``TokenEnded`` says it was cancelled."""
        with self._lock:
            terminal = self._terminal
            if terminal is None:
                return
            self._cancelled = True
        terminal.terminate(force=True)

    def _watch(self, terminal: Terminal, on_event: Callable[[TokenEvent], None]) -> None:
        text, token = "", ""
        told_url = False
        while True:
            try:
                chunk = terminal.read(4096)
            except EOFError, OSError:
                break
            text += chunk
            plain = plain_text(text)
            url = _URL.search(plain)
            if url and not told_url:
                told_url = True
                on_event(TokenUrl(url.group()))
            found = _TOKEN.search(plain)
            if found and not token:
                token = found.group()
                on_event(TokenReceived(token))
                timer = threading.Timer(_END_WAIT_SECONDS, self._stop_after_token, (terminal,))
                timer.daemon = True
                timer.start()
        with self._lock:
            cancelled = self._cancelled
            self._terminal = None
        on_event(TokenEnded(bool(token) and not cancelled, cancelled, _shown(plain_text(text))))

    @staticmethod
    def _stop_after_token(terminal: Terminal) -> None:
        """The token is there: a command that did not end by itself is ended."""
        if terminal.isalive():
            terminal.terminate(force=True)
