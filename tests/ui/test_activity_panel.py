from collections.abc import Iterator

import pytest
import wx

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
