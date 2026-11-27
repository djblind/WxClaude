"""The Activity field of the main window: what Claude and its subagents do while they answer, one
line per action (``docs/interface.md``, "Activity"; the lines: ``core/claude/activity.py``).

A read-only field, reached with Tab (after the buttons of the prompt) or its access key. A line
added never moves the focus nor the caret of the user: the text is appended at the end.
"""

import wx

from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _

_MAX_LINES = 5000  # beyond, the oldest lines are dropped


class ActivityPanel:
    """The label and the read-only field of the activity."""

    def __init__(self, parent: wx.Window) -> None:
        text = _("Activit&y")
        self.label = wx.StaticText(parent, label=text)
        style = wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_DONTWRAP
        self.field = wx.TextCtrl(parent, style=style, name=accessible_name(text))
        self.field.SetMinSize(wx.Size(-1, self.field.GetCharHeight() * 5 + 10))
        self._lines = 0

    def follow(self, control: wx.Window) -> None:
        """Come after ``control`` in the Tab order (the field is created before the prompt, which
        the user reaches first)."""
        self.label.MoveAfterInTabOrder(control)
        self.field.MoveAfterInTabOrder(self.label)

    def add_to(self, sizer: wx.BoxSizer) -> None:
        """Lay the label and the field out at the end of ``sizer``."""
        sizer.Add(self.label, 0, wx.LEFT, 6)
        sizer.Add(self.field, 1, wx.EXPAND | wx.ALL, 6)

    def append(self, line: str) -> None:
        """Add ``line`` at the end; the caret of the user does not move."""
        field = self.field
        caret = field.GetInsertionPoint()
        if self._lines >= _MAX_LINES:
            dropped = len(field.GetLineText(0)) + 1  # the first line and its line break
            field.Remove(0, dropped)
            caret = max(0, caret - dropped)
            self._lines -= 1
        field.AppendText(line if self._lines == 0 else "\n" + line)
        self._lines += 1
        if field.HasFocus():
            field.SetInsertionPoint(caret)  # the user reads: the new line does not move them

    def clear(self) -> None:
        """Empty the field."""
        self.field.Clear()
        self._lines = 0

    @property
    def text(self) -> str:
        """The lines shown, separated by line breaks."""
        return str(self.field.GetValue())
