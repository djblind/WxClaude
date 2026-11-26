"""Dialog to sign in to another account of Claude: the view of
``presenters/account_sign_in_presenter.py``.

The sign-in starts when the dialog opens and the browser opens by itself. The focus is on the
progress, which says what to do; then on the field Code once the page is open. Everything is
reachable by keyboard. ``token`` holds the result when the dialog ends with OK.
"""

from collections.abc import Callable

import wx

from wxclaude.core.claude.account_token import AccountSignIn, TokenEvent
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _
from wxclaude.presenters.account_sign_in_presenter import AccountSignInPresenter
from wxclaude.ui import desktop
from wxclaude.ui.fields import read_only_field


class AccountSignInDialog(wx.Dialog):
    """Progress, address of the page, the field Code and the buttons Send, Open, Copy, Close."""

    def __init__(self, parent: wx.Window, name: str, sign_in: AccountSignIn) -> None:
        super().__init__(
            parent,
            title=_("Sign in to the Claude account {name}").format(name=name),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.token = ""
        self._url = ""
        self._presenter = AccountSignInPresenter(sign_in, self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._progress = self._add_field(sizer, _("Sign-in progress"), 4)
        self._address = self._add_field(sizer, _("Address of the sign-in page"), 3)
        code_text = _("C&ode")
        self._add_label(sizer, code_text)
        self._code = wx.TextCtrl(self, style=wx.TE_PASSWORD, name=accessible_name(code_text))
        sizer.Add(self._code, 0, wx.EXPAND | wx.ALL, 8)

        self._send = wx.Button(self, label=_("&Send the code"))
        self._open = wx.Button(self, label=_("Open the page in the &browser"))
        self._copy = wx.Button(self, label=_("Copy the &address"))
        close = wx.Button(self, wx.ID_CLOSE)
        self._send.Bind(wx.EVT_BUTTON, lambda _event: self._presenter.send_code(self._code_text))
        self._open.Bind(wx.EVT_BUTTON, lambda _event: self._on_open())
        self._copy.Bind(wx.EVT_BUTTON, lambda _event: self._on_copy())
        close.Bind(wx.EVT_BUTTON, lambda _event: self._on_close())
        self.Bind(wx.EVT_CLOSE, lambda _event: self._on_close())
        self.SetEscapeId(wx.ID_CLOSE)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for button in (self._send, self._open, self._copy, close):
            buttons.Add(button, 0, wx.RIGHT, 6)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizerAndFit(sizer)

        self._open.Enable(False)
        self._copy.Enable(False)
        self.ask_code(False)
        self._presenter.start()
        self._progress.SetFocus()

    @property
    def _code_text(self) -> str:
        return str(self._code.GetValue())

    def _add_label(self, sizer: wx.BoxSizer, text: str) -> None:
        """A label, created right before its control so that screen readers pair them."""
        sizer.Add(wx.StaticText(self, label=text), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

    def _add_field(self, sizer: wx.BoxSizer, text: str, lines: int) -> wx.TextCtrl:
        self._add_label(sizer, text)
        field = read_only_field(self, lines, name=accessible_name(text))
        field.SetMinSize(wx.Size(field.GetCharWidth() * 70, field.GetMinSize().GetHeight()))
        sizer.Add(field, 0, wx.EXPAND | wx.ALL, 8)
        return field

    def _on_open(self) -> None:
        if not wx.LaunchDefaultBrowser(self._url):
            self.show_error(_("The browser could not be opened."))

    def _on_copy(self) -> None:
        if not desktop.set_clipboard(self._url):
            self.show_error(_("The address could not be copied."))

    def _on_close(self) -> None:
        """Closing stops a sign-in that is still running."""
        self._presenter.close()
        self.EndModal(wx.ID_CLOSE)

    # The view of the presenter ------------------------------------------------------------------

    def call_after(self, function: Callable[[TokenEvent], None], event: TokenEvent) -> None:
        wx.CallAfter(function, event)

    def set_progress(self, text: str) -> None:
        self._progress.SetValue(text)

    def show_url(self, url: str) -> None:
        self._url = url
        self._address.SetValue(url)
        self._open.Enable(True)
        self._copy.Enable(True)

    def ask_code(self, enabled: bool) -> None:
        """The field Code and Send follow; the focus goes to the field when it can be typed in."""
        self._code.Enable(enabled)
        self._send.Enable(enabled)
        if enabled:
            self._send.SetDefault()
            self._code.SetFocus()

    def finish(self, token: str) -> None:
        self.token = token
        self.EndModal(wx.ID_OK)

    def show_error(self, message: str) -> None:
        with wx.MessageDialog(self, message, _("Error"), wx.OK | wx.ICON_ERROR) as dialog:
            dialog.ShowModal()
