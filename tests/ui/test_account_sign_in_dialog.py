"""The sign-in to another account of Claude: the form of the provider and the dialog (a fake
console, no browser, no modal loop)."""

from pathlib import Path

import pytest
import wx
from fake_vault import FakeVault

from wxclaude.core.claude.account_token import AccountSignIn, TokenUrl
from wxclaude.core.config.providers import ENGINE_ACCOUNT, Provider, ProviderStore
from wxclaude.presenters.provider_form_presenter import ProviderEdit
from wxclaude.ui.account_sign_in_dialog import AccountSignInDialog
from wxclaude.ui.provider_dialogs import ProviderDialog

pytestmark = pytest.mark.ui


class SilentTerminal:
    """A console that prints nothing until it is ended."""

    def __init__(self) -> None:
        self.ended = False

    def read(self, size: int = 4096) -> str:
        while not self.ended:
            wx.MilliSleep(20)
        raise EOFError

    def write(self, text: str) -> int:
        return len(text)

    def isalive(self) -> bool:
        return not self.ended

    def terminate(self, force: bool = False) -> bool:
        self.ended = True
        return True


def test_the_form_of_an_account_signs_in(wx_app: wx.App, tmp_path: Path) -> None:
    store = ProviderStore(FakeVault(), tmp_path / "providers.json")
    account = Provider(id="compte-2", name="Compte 2", engine=ENGINE_ACCOUNT)
    dialog = ProviderDialog(None, store, ProviderEdit(account))
    try:
        assert dialog._engine.GetStringSelection() == "Claude account (another account of a plan)"
        assert dialog._key_button.GetLabel() == "&Sign in to the account"
        assert not dialog._check_button.IsEnabled()
        assert dialog.result.provider.is_account
    finally:
        dialog.Destroy()


def test_the_dialog_shows_the_page_and_asks_the_code(wx_app: wx.App) -> None:
    terminal = SilentTerminal()
    sign_in = AccountSignIn(["claude"], spawn=lambda argv, env: terminal)
    dialog = AccountSignInDialog(None, "Compte 2", sign_in)
    try:
        assert dialog.GetTitle() == "Sign in to the Claude account Compte 2"
        assert dialog._code.GetName() == "Code"
        assert not dialog._code.IsEnabled()
        dialog._presenter._on_event(TokenUrl("https://claude.com/page"))
        assert dialog._address.GetValue() == "https://claude.com/page"
        assert dialog._code.IsEnabled()
        assert dialog._copy.IsEnabled()
    finally:
        dialog._presenter.close()
        dialog.Destroy()
    assert terminal.ended
