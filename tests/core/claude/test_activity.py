import pytest

from wxclaude.core.claude.activity import ActivityLog
from wxclaude.core.claude.events import AssistantText, Thinking, ToolResult, ToolUsed

pytestmark = pytest.mark.unit


def test_a_tool_is_shown_with_what_it_works_on() -> None:
    log = ActivityLog()
    bash = ToolUsed("t1", "Bash", {"command": "python -I verif.py\n--all", "description": "x"})
    assert log.line_for(bash, "Claude") == "Claude: Bash python -I verif.py --all"
    read = ToolUsed("t2", "Read", {"file_path": "D:/ff4/SUIVI_FF4.txt"})
    assert log.line_for(read, "Claude") == "Claude: Read D:/ff4/SUIVI_FF4.txt"
    assert log.line_for(ToolUsed("t3", "TodoWrite", {"todos": []}), "Claude") == "Claude: TodoWrite"


def test_the_text_of_claude_is_on_one_line_and_cut_when_long() -> None:
    log = ActivityLog()
    assert log.line_for(AssistantText("I check\nthe files.", "m"), "Claude") == (
        "Claude: I check the files."
    )
    line = log.line_for(AssistantText("x" * 500, "m"), "Claude")
    assert line is not None
    assert len(line) == len("Claude: ") + 300
    assert line.endswith("…")


def test_a_subagent_is_named_after_its_type_in_what_it_does() -> None:
    log = ActivityLog()
    launch = ToolUsed(
        "a1", "Agent", {"subagent_type": "traducteur", "description": "Translate dial_zh_03"}
    )
    assert log.line_for(launch, "Claude") == (
        "Claude launches the subagent traducteur: Translate dial_zh_03"
    )
    inside = ToolUsed("t9", "Write", {"file_path": "dial_zh_03.json"}, parent="a1")
    assert log.line_for(inside, "Claude") == "Subagent traducteur: Write dial_zh_03.json"
    said = AssistantText("Done: 729 entries.", "claude-sonnet-5-5", parent="a1")
    assert log.line_for(said, "Claude") == "Subagent traducteur: Done: 729 entries."
    unknown = AssistantText("Hello", "m", parent="other")
    assert log.line_for(unknown, "Claude") == "Subagent: Hello"


def test_a_failed_tool_is_said_and_the_rest_says_nothing() -> None:
    log = ActivityLog()
    log.line_for(ToolUsed("t1", "Bash", {"command": "ls"}), "DeepSeek")
    assert log.line_for(ToolResult("t1", True), "DeepSeek") == "DeepSeek: the tool Bash failed."
    assert log.line_for(ToolResult("t1", False), "DeepSeek") is None
    assert log.line_for(Thinking(), "DeepSeek") is None


def test_a_line_is_not_repeated_and_a_new_message_forgets_the_subagents() -> None:
    log = ActivityLog()
    read = ToolUsed("t1", "Read", {"file_path": "a.txt"})
    assert log.line_for(read, "Claude") is not None
    assert log.line_for(ToolUsed("t2", "Read", {"file_path": "a.txt"}), "Claude") is None
    log.line_for(ToolUsed("a1", "Agent", {"subagent_type": "chercheur"}), "Claude")
    log.start()
    assert log.line_for(AssistantText("x", "m", parent="a1"), "Claude") == "Subagent: x"
