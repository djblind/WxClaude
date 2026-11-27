"""The wx side of a message sent to Claude: the view of ``presenters/run_presenter.py``."""

import time
from collections.abc import Callable

import wx

from wxclaude.core.claude.events import PermissionRequest, RunEvent
from wxclaude.core.claude.permissions import Decision
from wxclaude.core.claude.questions import Question
from wxclaude.core.conversation.messages import Message
from wxclaude.core.speech.announcements import PROGRESS, Announce, AnnouncementCenter
from wxclaude.ui.activity_panel import ActivityPanel
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.permission_dialog import PermissionDialog
from wxclaude.ui.question_dialog import QuestionDialog

_PROGRESS_GAP = 5.0  # seconds between two frequent progresses spoken
#: The progress that comes at every step of a long work.
_FREQUENT = frozenset(
    {
        Announce.CLAUDE_THINKING,
        Announce.CLAUDE_USING_TOOL,
        Announce.CLAUDE_USING_TOOL_ON,
        Announce.CLAUDE_USING_TOOL_TO_RUN,
        Announce.CLAUDE_ANSWERING,
    }
)


class WxRunView:
    """Shows a run in the conversation view and the status bar, asks with the permission dialog.

    ``parent`` is the window of the dialogs; ``activity`` is the Activity field.
    """

    def __init__(
        self,
        parent: wx.Window,
        view: ConversationView,
        feedback: Feedback,
        activity: ActivityPanel,
    ) -> None:
        self._parent = parent
        self._view = view
        self._feedback = feedback
        self._activity = activity
        self._last_progress = -_PROGRESS_GAP  # when a progress was last spoken (monotonic)
        self._open_question: tuple[PermissionRequest, wx.Dialog] | None = None

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        """Hand the event over to the interface thread."""
        wx.CallAfter(function, event)

    def append_message(self, message: Message) -> None:
        self._view.append_message(message)

    def show_session(self, messages: list[Message]) -> None:
        """Show the messages of the session file if they differ from the view; the caret stays."""
        view = self._view
        if view.shows(messages):
            view.adopt_details(messages)  # the messages shown live have no tools yet
        else:
            view.replace_messages(messages)

    def ask_permission(self, request: PermissionRequest, wait_text: str = "") -> Decision:
        """Show the question; closing the dialog without answering is a denial."""
        with PermissionDialog(self._parent, request, wait_text) as dialog:
            self._open_question = (request, dialog)
            try:
                self._feedback.modal(dialog)
            finally:
                self._open_question = None
            decision: Decision = dialog.decision
        return decision

    def ask_questions(self, questions: list[Question]) -> dict[str, list[str]] | None:
        """Show the questions of Claude; None if the user refused to answer."""
        with QuestionDialog(self._parent, questions) as dialog:
            self._feedback.modal(dialog)
            if not dialog.sent:
                return None
            answers: dict[str, list[str]] = dialog.answers
        return answers

    def close_permission(self, request_id: str) -> None:
        question = self._open_question
        if question is not None and question[0].request_id == request_id:
            question[1].EndModal(wx.ID_NO)

    def say(self, announce: Announce, **values: object) -> None:
        """Announce. The progress (thinking, a tool...) comes many times a minute during a long
        work: it is spoken only while the user is in the main window but not in the Activity
        field (which shows the same thing), and the frequent ones (``_FREQUENT``) at most once
        every ``_PROGRESS_GAP`` seconds; otherwise it is only written in the status bar, so that
        the screen reader is not cut in a dialog, in another application or while the user
        reads."""
        if announce.category is PROGRESS and not self._progress_spoken(announce):
            self._feedback.set_status(AnnouncementCenter.text(announce, **values))
            return
        self._feedback.say(announce, **values)

    def _progress_spoken(self, announce: Announce) -> bool:
        """May the progress ``announce`` be spoken now? (A frequent one is then counted.)"""
        focused = wx.Window.FindFocus()
        in_window = focused is not None and focused.GetTopLevelParent() is self._parent
        if not in_window or focused is self._activity.field:
            return False
        if announce not in _FREQUENT:
            return True  # an interruption, a retry of the server, a model that loads: rare
        now = time.monotonic()
        if now - self._last_progress < _PROGRESS_GAP:
            return False
        self._last_progress = now
        return True

    def set_status(self, text: str) -> None:
        self._feedback.set_status(text)

    def show_step(self, text: str) -> None:
        self._feedback.show_step(text)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)

    def show_activity(self, line: str) -> None:
        self._activity.append(line)

    def clear_activity(self) -> None:
        self._activity.clear()
