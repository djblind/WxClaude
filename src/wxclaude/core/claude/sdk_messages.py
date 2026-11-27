"""The messages of the Agent SDK, given back the shape of the ``stream-json`` lines of the CLI.

The SDK reads the same lines as ``core/claude/stream.py`` and turns them into objects. Each object
is written back here as the line it came from (only the fields WxClaude reads), so that one parser,
``stream.parse_stream_entry``, makes the events of both engines. This module imports the SDK: it is
only imported when a message goes through it (``sdk_run.py``).
"""

from claude_agent_sdk import (
    AssistantMessage,
    Message,
    RateLimitEvent,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from wxclaude.core.claude.events import RunEvent
from wxclaude.core.claude.stream import parse_stream_entry


def events_of(message: Message) -> list[RunEvent]:
    """The events of one message of the SDK (none for a kind WxClaude does not use)."""
    entry = stream_entry(message)
    return parse_stream_entry(entry) if entry is not None else []


def stream_entry(message: Message) -> dict[str, object] | None:
    """The ``stream-json`` object ``message`` was read from, as far as WxClaude reads it."""
    if isinstance(message, SystemMessage):
        return {**message.data, "type": "system", "subtype": message.subtype}
    if isinstance(message, AssistantMessage):
        content = [block for block in map(_assistant_block, message.content) if block]
        return {
            "type": "assistant",
            "parent_tool_use_id": message.parent_tool_use_id,
            "message": {"model": message.model, "content": content, "usage": message.usage},
        }
    if isinstance(message, UserMessage):
        blocks = message.content if isinstance(message.content, list) else []
        results = [
            {"type": "tool_result", "tool_use_id": block.tool_use_id, "is_error": block.is_error}
            for block in blocks
            if isinstance(block, ToolResultBlock)
        ]
        return {"type": "user", "message": {"content": results}}
    if isinstance(message, ResultMessage):
        return _result(message)
    if isinstance(message, RateLimitEvent):
        return {"type": "rate_limit_event", "rate_limit_info": message.rate_limit_info.raw}
    return None


def _assistant_block(block: object) -> dict[str, object] | None:
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ThinkingBlock):
        return {"type": "thinking"}
    if isinstance(block, ToolUseBlock):
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return None


def _result(message: ResultMessage) -> dict[str, object]:
    return {
        "type": "result",
        "subtype": message.subtype,
        "is_error": message.is_error,
        "result": message.result,
        "usage": message.usage,
        "duration_ms": message.duration_ms,
        "total_cost_usd": message.total_cost_usd,
        "num_turns": message.num_turns,
    }
