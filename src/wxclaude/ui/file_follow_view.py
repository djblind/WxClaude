"""The wx side of Tools > Follow a file (``presenters/file_follow_presenter.py``): the choice of the
file, the lines added to the Activity field, and the timer that looks at the files every second."""

from collections.abc import Callable
from pathlib import Path

import wx

from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _
from wxclaude.ui.activity_panel import ActivityPanel
from wxclaude.ui.feedback import Feedback

_LOOK_MILLISECONDS = 1000


class WxFileFollowView:
    """``parent`` owns the dialog and the timer; ``tick`` is called at every look."""

    def __init__(
        self,
        parent: wx.Window,
        feedback: Feedback,
        activity: ActivityPanel,
        tick: Callable[[], None],
    ) -> None:
        self._parent = parent
        self._feedback = feedback
        self._activity = activity
        self._timer = wx.Timer(parent)
        parent.Bind(wx.EVT_TIMER, lambda _event: tick(), self._timer)

    def choose_file(self, folder: Path | None) -> Path | None:
        with wx.FileDialog(
            self._parent,
            _("Choose the file to follow"),
            defaultDir=str(folder) if folder is not None else "",
            wildcard=_("Logs (*.log;*.txt)|*.log;*.txt|All files (*.*)|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return None
            return Path(dialog.GetPath())

    def show_activity(self, line: str) -> None:
        self._activity.append(line)

    def say(self, announce: Announce, **values: object) -> None:
        self._feedback.say(announce, **values)

    def start_timer(self) -> None:
        self._timer.Start(_LOOK_MILLISECONDS)

    def stop_timer(self) -> None:
        self._timer.Stop()
