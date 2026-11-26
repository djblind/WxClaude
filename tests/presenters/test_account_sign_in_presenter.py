"""The dialog of the sign-in to another account of Claude, with a fake view and a fake console."""

from collections.abc import Callable

import pytest

from wxclaude.core.claude.account_token import (
    AccountSignIn,
    TokenEnded,
    TokenEvent,
    TokenReceived,
    TokenUrl,
)
from wxclaude.core.errors import ClaudeLoginError
from wxclaude.presenters.account_sign_in_presenter import AccountSignInPresenter

pytestmark = pytest.mark.unit

TOKEN = "sk-ant-oat01-token"


class FakeSignIn(AccountSignIn):
    """Records the calls; the test sends the events itself."""

    def __init__(self, *, fails: bool = False) -> None:
        super().__init__(["claude"])
        self.fails = fails
        self.post: Callable[[TokenEvent], None] | None = None
        self.codes: list[str] = []
        self.cancelled = False

    def start(self, on_event: Callable[[TokenEvent], None]) -> None:
        if self.fails:
            raise ClaudeLoginError("no claude")
        self.post = on_event

    def send_code(self, code: str) -> None:
        self.codes.append(code)

    def cancel(self) -> None:
        self.cancelled = True


class FakeView:
    def __init__(self) -> None:
        self.progress = ""
        self.url = ""
        self.code_enabled: bool | None = None
        self.token: str | None = None
        self.errors: list[str] = []

    def call_after(self, function: Callable[[TokenEvent], None], event: TokenEvent) -> None:
        function(event)

    def set_progress(self, text: str) -> None:
        self.progress = text

    def show_url(self, url: str) -> None:
        self.url = url

    def ask_code(self, enabled: bool) -> None:
        self.code_enabled = enabled

    def finish(self, token: str) -> None:
        self.token = token

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def started(
    sign_in: FakeSignIn | None = None,
) -> tuple[AccountSignInPresenter, FakeSignIn, FakeView]:
    sign_in = sign_in or FakeSignIn()
    view = FakeView()
    presenter = AccountSignInPresenter(sign_in, view)
    presenter.start()
    return presenter, sign_in, view


def test_the_page_then_the_code_then_the_token() -> None:
    presenter, sign_in, view = started()
    assert view.code_enabled is False
    assert sign_in.post is not None
    sign_in.post(TokenUrl("https://claude.com/x"))
    assert view.url == "https://claude.com/x"
    assert view.code_enabled is True
    assert "paste it" in view.progress
    presenter.send_code("  ")
    assert view.errors == ["Paste the code that the page of Claude shows."]
    presenter.send_code("abc#def")
    assert sign_in.codes == ["abc#def"]
    assert view.code_enabled is False
    sign_in.post(TokenReceived(TOKEN))
    sign_in.post(TokenEnded(True, False, ""))
    assert view.token == TOKEN


def test_a_failure_is_said_and_gives_no_token() -> None:
    _presenter, sign_in, view = started()
    assert sign_in.post is not None
    sign_in.post(TokenEnded(False, False, "OAuth error: invalid code"))
    assert view.token is None
    assert view.errors == ["The sign-in failed.\nOAuth error: invalid code"]


def test_closing_cancels_and_ignores_what_comes_after() -> None:
    presenter, sign_in, view = started()
    presenter.close()
    assert sign_in.cancelled
    assert sign_in.post is not None
    sign_in.post(TokenReceived(TOKEN))
    sign_in.post(TokenEnded(False, True, ""))
    assert view.token is None


def test_a_command_that_cannot_start_is_said() -> None:
    _presenter, _sign_in, view = started(FakeSignIn(fails=True))
    assert view.errors == ["The sign-in cannot be started.\nno claude"]
