"""Tools > Follow a file: the new lines of files chosen by the user go to the Activity field, for
a long work that runs without Claude (a build, a test bench, a translation...). It costs no token.
See ``docs/interface.md``, "Following a file". Nothing here touches wx.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from wxclaude.core.file_follower import FileFollower
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _


class FileFollowView(Protocol):
    """What the presenter asks of the interface."""

    def choose_file(self, folder: Path | None) -> Path | None:
        """Let the user choose a file to follow, starting in ``folder``; None if cancelled."""
        ...

    def show_activity(self, line: str) -> None:
        """Add a line at the end of the Activity field."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def start_timer(self) -> None:
        """Call ``tick`` regularly (every second) until ``stop_timer``."""
        ...

    def stop_timer(self) -> None:
        """No more ``tick``."""
        ...


class FileFollowPresenter:
    """The files followed and their new lines; ``workspace`` is where the choice starts."""

    def __init__(self, view: FileFollowView, workspace: Callable[[], Path | None]) -> None:
        self._view = view
        self._workspace = workspace
        self._followers: list[FileFollower] = []

    @property
    def following(self) -> bool:
        """Is a file followed?"""
        return bool(self._followers)

    def follow(self) -> None:
        """Ask for a file and follow it: its last lines at once, then its new lines."""
        path = self._view.choose_file(self._workspace())
        if path is None:
            return
        if any(follower.path == path for follower in self._followers):
            self._view.say(Announce.FILE_ALREADY_FOLLOWED, file=path.name)
            return
        follower = FileFollower(path)
        self._followers.append(follower)
        self._show(follower)
        self._view.say(Announce.FILE_FOLLOWED, file=path.name)
        if len(self._followers) == 1:
            self._view.start_timer()

    def tick(self) -> None:
        """A look at the files followed: their new lines go to the Activity field."""
        for follower in self._followers:
            self._show(follower)

    def stop(self) -> None:
        """Follow no file any more."""
        if not self._followers:
            self._view.say(Announce.NO_FILE_FOLLOWED)
            return
        self._followers.clear()
        self._view.stop_timer()
        self._view.say(Announce.FILES_NO_LONGER_FOLLOWED)

    def close(self) -> None:
        """The window closes: the timer stops, without a word."""
        if self._followers:
            self._followers.clear()
            self._view.stop_timer()

    def _show(self, follower: FileFollower) -> None:
        for line in follower.new_lines():
            self._view.show_activity(_("{file}: {line}").format(file=follower.path.name, line=line))
