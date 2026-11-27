"""What Claude does while it answers, one line per action, for the Activity field
(``docs/interface.md``, "Activity").

Everything comes from the stream the CLI already sends (no token is spent for it): the tools called
with what they work on, the text Claude writes between two actions, and the same for the subagents,
named after their type (``Agent`` tool, ``subagent_type``). The thinking of the model is not given
in its text by the CLI (the blocks are empty), so it is not shown.
"""

from wxclaude.core.claude.events import AssistantText, RunEvent, ToolResult, ToolUsed
from wxclaude.i18n import _

_AGENT_TOOLS = frozenset({"Agent", "Task"})
#: The keys of the input of a tool that say what it works on, the first one found is shown.
_TARGET_KEYS = (
    "command",
    "file_path",
    "notebook_path",
    "path",
    "pattern",
    "url",
    "query",
    "skill",
    "description",
    "prompt",
)
_LONGEST = 300  # characters of a line, beyond which it is cut


def _one_line(text: str, longest: int = _LONGEST) -> str:
    """``text`` on one line (spaces in place of the line breaks), cut at ``longest`` characters."""
    flat = " ".join(text.split())
    return flat if len(flat) <= longest else flat[: longest - 1] + "…"


def _target(tool_input: dict[str, object]) -> str:
    """What a tool works on: its command, its file, its pattern... ('' when nothing says it)."""
    for key in _TARGET_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


class ActivityLog:
    """Turns the events of a run into lines; remembers the subagents launched, by their call."""

    def __init__(self) -> None:
        self._agents: dict[str, str] = {}  # call of the Agent tool -> type of the subagent
        self._tools: dict[str, str] = {}  # call of a tool -> its name
        self._last = ""

    def start(self) -> None:
        """A new message: what was remembered of the last one is forgotten."""
        self._agents.clear()
        self._tools.clear()
        self._last = ""

    def line_for(self, event: RunEvent, speaker: str) -> str | None:
        """The line of ``event`` (``speaker`` names the main conversation), None when it says
        nothing or repeats the line before."""
        line = self._line(event, speaker)
        if line is None or line == self._last:
            return None
        self._last = line
        return line

    def _line(self, event: RunEvent, speaker: str) -> str | None:
        if isinstance(event, ToolUsed):
            return self._tool_line(event, self._who(event.parent, speaker))
        if isinstance(event, AssistantText):
            text = _one_line(event.text)
            if not text:
                return None
            return _("{who}: {text}").format(who=self._who(event.parent, speaker), text=text)
        if isinstance(event, ToolResult) and event.is_error and event.tool_id in self._tools:
            return _("{who}: the tool {tool} failed.").format(
                who=self._who(event.parent, speaker), tool=self._tools[event.tool_id]
            )
        return None

    def _tool_line(self, event: ToolUsed, who: str) -> str:
        if event.name in _AGENT_TOOLS:
            agent = _agent_type(event.input)
            self._agents[event.tool_id] = agent
            task = _one_line(_target(event.input))
            if task:
                return _("{who} launches the subagent {agent}: {task}").format(
                    who=who, agent=agent, task=task
                )
            return _("{who} launches the subagent {agent}").format(who=who, agent=agent)
        self._tools[event.tool_id] = event.name
        target = _one_line(_target(event.input))
        if target:
            return _("{who}: {tool} {target}").format(who=who, tool=event.name, target=target)
        return _("{who}: {tool}").format(who=who, tool=event.name)

    def _who(self, parent: str, speaker: str) -> str:
        """Who does it: the main conversation, or the subagent of the call ``parent``."""
        if not parent:
            return speaker
        agent = self._agents.get(parent)
        if agent is None:
            return _("Subagent")
        return _("Subagent {agent}").format(agent=agent)


def _agent_type(tool_input: dict[str, object]) -> str:
    """The type of the subagent a call of the ``Agent`` tool launches."""
    value = tool_input.get("subagent_type")
    return value if isinstance(value, str) and value else "general-purpose"
