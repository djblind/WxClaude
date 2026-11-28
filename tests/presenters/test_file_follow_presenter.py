"""Tools > Follow a file: the new lines of the files chosen go to the Activity field."""

from pathlib import Path

import pytest

from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.file_follow_presenter import FileFollowPresenter

pytestmark = pytest.mark.unit


class FakeView:
    def __init__(self, choices: list[Path | None]) -> None:
        self.choices = choices
        self.lines: list[str] = []
        self.said: list[Announce] = []
        self.timer = False
        self.folders: list[Path | None] = []

    def choose_file(self, folder: Path | None) -> Path | None:
        self.folders.append(folder)
        return self.choices.pop(0)

    def show_activity(self, line: str) -> None:
        self.lines.append(line)

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append(announce)

    def start_timer(self) -> None:
        self.timer = True

    def stop_timer(self) -> None:
        self.timer = False


def test_a_file_followed_shows_its_last_lines_then_its_new_ones(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    log.write_text("start\n", encoding="utf-8")
    view = FakeView([log])
    presenter = FileFollowPresenter(view, lambda: tmp_path)
    presenter.follow()
    assert view.folders == [tmp_path]
    assert view.lines == ["work.log: start"]
    assert view.said == [Announce.FILE_FOLLOWED]
    assert view.timer
    presenter.tick()
    assert view.lines == ["work.log: start"]  # nothing new
    with log.open("a", encoding="utf-8") as handle:
        handle.write("[2/43] lot\n")
    presenter.tick()
    assert view.lines[-1] == "work.log: [2/43] lot"


def test_the_same_file_twice_and_a_cancelled_choice(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    log.write_text("", encoding="utf-8")
    view = FakeView([log, log, None])
    presenter = FileFollowPresenter(view, lambda: None)
    presenter.follow()
    presenter.follow()
    presenter.follow()
    assert view.said == [Announce.FILE_FOLLOWED, Announce.FILE_ALREADY_FOLLOWED]


def test_stop_follows_nothing_more_and_says_it(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    log.write_text("", encoding="utf-8")
    view = FakeView([log])
    presenter = FileFollowPresenter(view, lambda: None)
    presenter.stop()
    assert view.said == [Announce.NO_FILE_FOLLOWED]
    presenter.follow()
    presenter.stop()
    assert not view.timer
    assert not presenter.following
    assert view.said[-1] is Announce.FILES_NO_LONGER_FOLLOWED
