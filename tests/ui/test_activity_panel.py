import time
from collections.abc import Iterator

import pytest
import wx

from wxclaude.core.speech.announcements import Announce
from wxclaude.ui.activity_panel import ActivityPanel
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


@pytest.fixture
def panel(wx_app: wx.App) -> Iterator[ActivityPanel]:
    frame = wx.Frame(None)
    yield ActivityPanel(frame)
    frame.Destroy()
    wx.SafeYield()


def test_lines_are_appended_and_cleared(panel: ActivityPanel) -> None:
    panel.append("one")
    panel.append("two")
    assert panel.text == "one\ntwo"
    panel.clear()
    panel.append("three")
    assert panel.text == "three"


def test_the_field_is_named_and_read_only(panel: ActivityPanel) -> None:
    assert panel.field.GetName() == "Activity"
    assert not panel.field.IsEditable()


def test_the_activity_comes_after_the_prompt_in_the_tab_order(window: MainWindow) -> None:
    order = list(window._prompt.GetParent().GetChildren())
    assert order.index(window._activity.field) > order.index(window._prompt)
    assert order.index(window._activity.field) == order.index(window._activity.label) + 1


def test_the_progress_is_not_spoken_while_the_user_reads_the_activity(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    spoken: list[Announce] = []
    monkeypatch.setattr(window._feedback, "say", lambda announce, **values: spoken.append(announce))
    window._activity.field.SetFocus()
    window._run_view.say(Announce.CLAUDE_THINKING, name="Claude")
    window._run_view.say(Announce.CLAUDE_DONE, name="Claude")
    assert spoken == [Announce.CLAUDE_DONE]  # the end is still said
    window._activity.field.Navigate()  # the focus leaves the field
    window._run_view.say(Announce.CLAUDE_THINKING, name="Claude")
    assert spoken[-1] is Announce.CLAUDE_THINKING


def test_the_frequent_progress_is_spoken_once_every_five_seconds_and_not_in_a_dialog(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    spoken: list[Announce] = []
    monkeypatch.setattr(window._feedback, "say", lambda announce, **values: spoken.append(announce))
    clock = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    window._conversation.SetFocus()  # the prompt is greyed: no conversation
    view = window._run_view
    view.say(Announce.CLAUDE_THINKING, name="Claude")
    view.say(Announce.CLAUDE_USING_TOOL, name="Claude", tool="Bash")  # too soon
    view.say(Announce.CLAUDE_INTERRUPTING, name="Claude")  # rare: always said
    clock[0] += 6
    view.say(Announce.CLAUDE_USING_TOOL, name="Claude", tool="Bash")
    assert spoken == [
        Announce.CLAUDE_THINKING,
        Announce.CLAUDE_INTERRUPTING,
        Announce.CLAUDE_USING_TOOL,
    ]
    dialog = wx.Dialog(window)
    button = wx.Button(dialog)
    button.SetFocus()
    clock[0] += 6
    view.say(Announce.CLAUDE_THINKING, name="Claude")
    dialog.Destroy()
    assert spoken[-1] is Announce.CLAUDE_USING_TOOL  # nothing spoken in the dialog
