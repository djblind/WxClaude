"""Signing in to another account of Claude from the form of a provider (``docs/providers.md``,
"Accounts of Claude"): ``claude setup-token`` runs in a thread (``core/claude/account_token.py``),
the user allows the account in the browser and pastes the code the page shows, and the token comes
back to the form, which saves it as the key of the provider with OK. Nothing here touches wx.
"""

from collections.abc import Callable
from typing import Protocol

from wxclaude.core.claude.account_token import (
    AccountSignIn,
    TokenEnded,
    TokenEvent,
    TokenReceived,
    TokenUrl,
)
from wxclaude.core.errors import ClaudeLoginError
from wxclaude.i18n import _


class AccountSignInView(Protocol):
    """What the presenter asks of the dialog."""

    def call_after(self, function: Callable[[TokenEvent], None], event: TokenEvent) -> None:
        """Call ``function(event)`` later on the interface thread (from any thread)."""
        ...

    def set_progress(self, text: str) -> None:
        """What the sign-in is doing, or what to do now."""
        ...

    def show_url(self, url: str) -> None:
        """The address of the sign-in page, to open it again or in another browser."""
        ...

    def ask_code(self, enabled: bool) -> None:
        """Whether the code of the page can be typed and sent."""
        ...

    def finish(self, token: str) -> None:
        """The sign-in succeeded: close the dialog and give ``token`` to the form."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class AccountSignInPresenter:
    """One sign-in, shown through ``view``, started when the dialog opens."""

    def __init__(self, sign_in: AccountSignIn, view: AccountSignInView) -> None:
        self._sign_in = sign_in
        self._view = view
        self._token = ""
        self._closed = False

    def start(self) -> None:
        """Start the command; the browser opens by itself."""
        self._token = ""
        try:
            self._sign_in.start(self._post)
        except ClaudeLoginError as error:
            self._view.show_error(_("The sign-in cannot be started.\n{error}").format(error=error))
            return
        self._view.ask_code(False)
        self._view.set_progress(_("Opening the sign-in page of Claude in the browser…"))

    def send_code(self, code: str) -> None:
        """The user pasted the code that the page of Claude shows."""
        if not code.strip():
            self._view.show_error(_("Paste the code that the page of Claude shows."))
            return
        try:
            self._sign_in.send_code(code)
        except ClaudeLoginError as error:
            self._view.show_error(_("The code cannot be sent.\n{error}").format(error=error))
            return
        self._view.ask_code(False)
        self._view.set_progress(_("Code sent. Waiting for Claude Code."))

    def close(self) -> None:
        """The dialog closes: stop what runs and ignore what comes after."""
        self._closed = True
        self._sign_in.cancel()

    def _post(self, event: TokenEvent) -> None:
        """Called by the thread of the command: hand the event over to the interface thread."""
        self._view.call_after(self._on_event, event)

    def _on_event(self, event: TokenEvent) -> None:
        if self._closed:
            return
        if isinstance(event, TokenUrl):
            self._view.show_url(event.url)
            self._view.ask_code(True)
            self._view.set_progress(
                _(
                    "In the browser, sign in with the account to add and allow it. Then copy the "
                    "code that the page shows, paste it in the field Code and send it."
                )
            )
        elif isinstance(event, TokenReceived):
            self._token = event.token
        elif isinstance(event, TokenEnded):
            self._finish(event)

    def _finish(self, ended: TokenEnded) -> None:
        if self._token and not ended.cancelled:
            self._closed = True
            self._view.finish(self._token)
            return
        self._view.ask_code(False)
        if ended.cancelled:
            self._view.set_progress(_("The sign-in was cancelled."))
            return
        self._view.set_progress(_("The sign-in failed."))
        self._view.show_error(_("The sign-in failed.\n{details}").format(details=ended.output))
