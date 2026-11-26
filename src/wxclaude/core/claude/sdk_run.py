"""One message sent through the Claude Agent SDK (``docs/agent-sdk.md``).

A provider whose engine is the Agent SDK (``Provider.uses_sdk``) is paid by the API credits of a
plan, which the SDK may use and Claude Code may not. The official SDK (``claude-agent-sdk``) then
starts the CLI itself, as an application built on it: WxClaude gives it the claude program the user
chose, the same session, model, effort, permission mode and settings as for Claude Code, and the
full system prompt of Claude Code (the SDK leaves it out unless asked).

The SDK is asynchronous: each message has a thread of its own that runs an event loop. The events
are the ones of the CLI (``sdk_messages.py``), handed to ``on_event`` from that thread, and the run
always ends with ``TurnEnded``, as with Claude Code. A permission question waits in the loop for
``answer``, called by the interface thread; ``interrupt`` cancels the message, which closes the CLI.
This module never imports ``wx``; it imports the SDK only when a message is sent.
"""

import asyncio
import json
import os
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from wxclaude import __version__
from wxclaude.core.claude.events import PermissionRequest, RunEvent, TurnEnded
from wxclaude.core.claude.inline_settings import merge_settings
from wxclaude.core.claude.launch import (
    ProviderLaunch,
    blanked_variables,
    provider_environment,
    provider_settings,
    sends_effort,
)
from wxclaude.core.claude.stream import suggested_rule
from wxclaude.core.errors import RunnerError
from wxclaude.core.security.restricted import restricted_permission_mode, restricted_settings

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, PermissionResult
    from claude_agent_sdk.types import ToolPermissionContext

    from wxclaude.core.claude.runner import RunRequest

CLIENT_APP = f"WxClaude/{__version__}"  # how WxClaude names itself to the SDK
_ENTRYPOINT = "CLAUDE_CODE_ENTRYPOINT"  # the name of the caller, which only the SDK sets
# The settings the CLI reads when the folder is not trusted (``core/security/restricted.py``).
_RESTRICTED_SOURCES = ["user"]

ClientFactory = Callable[["ClaudeAgentOptions"], "ClaudeSDKClient"]


def sdk_available() -> bool:
    """Is the Agent SDK installed?"""
    try:
        import claude_agent_sdk  # noqa: F401, PLC0415 (only asked for)
    except ImportError:
        return False
    return True


def _session_options(request: RunRequest) -> dict[str, Any]:
    """Which session the message goes to, as for Claude Code (``runner._session_arguments``)."""
    if request.resume:
        return {"resume": request.session_id}
    if request.fork_from:
        return {"resume": request.fork_from, "fork_session": True, "session_id": request.session_id}
    return {"session_id": request.session_id}


def sdk_options(
    request: RunRequest,
    *,
    cli_path: str | None,
    can_use_tool: Callable[..., Any],
    stderr: Callable[[str], None],
    inherited: Mapping[str, str] | None = None,
) -> ClaudeAgentOptions:
    """The options of the SDK for ``request``: what ``runner.build_arguments`` gives Claude Code,
    and the key of the provider in the environment (never on the command line)."""
    from claude_agent_sdk import ClaudeAgentOptions  # noqa: PLC0415 (the SDK is optional)

    agent, launch = request.agent, request.provider
    if not (agent.model and agent.effort and agent.permission_mode):
        raise RunnerError("The agent must have a model, an effort and a permission mode.")
    parts = [provider_settings(launch)]
    if request.restricted:
        parts.append(restricted_settings(request.cwd))
    settings = merge_settings(*parts)
    environment = _changed_variables(launch, inherited)
    mode = (
        restricted_permission_mode(agent.permission_mode)
        if request.restricted
        else agent.permission_mode
    )
    return ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        model=agent.model,
        effort=cast(Any, agent.effort) if sends_effort(launch) else None,
        permission_mode=cast(Any, mode),
        max_turns=request.max_turns or None,
        cwd=request.cwd,
        cli_path=cli_path,
        settings=json.dumps(settings) if settings else None,
        setting_sources=cast(Any, _RESTRICTED_SOURCES) if request.restricted else None,
        env={**blanked_variables(environment, inherited), **environment},
        extra_args={"name": request.name} if request.name and not request.resume else {},
        can_use_tool=can_use_tool,
        stderr=stderr,
        client_app=CLIENT_APP,
        **_session_options(request),
    )


def _changed_variables(
    launch: ProviderLaunch | None, inherited: Mapping[str, str] | None
) -> dict[str, str]:
    """What the launch changes in the environment of WxClaude, and only that.

    The SDK starts from the environment of WxClaude, puts its own name in it
    (``CLAUDE_CODE_ENTRYPOINT``), then adds the ``env`` it is given. Giving it the whole environment
    would put back a name WxClaude inherited (``claude-desktop`` when it was started from the Claude
    application): the API would then take the message for one of Claude Code and refuse the credits
    (measured: "Credit balance is too low"). The name is never given, whatever happens.
    """
    source = os.environ if inherited is None else inherited
    environment = provider_environment(launch, source) or {}
    changed = {name: value for name, value in environment.items() if source.get(name) != value}
    changed.pop(_ENTRYPOINT, None)
    return changed


def _default_client(options: ClaudeAgentOptions) -> ClaudeSDKClient:
    from claude_agent_sdk import ClaudeSDKClient  # noqa: PLC0415 (the SDK is optional)

    return ClaudeSDKClient(options)


@dataclass(slots=True)
class _State:
    """What the thread of the message and the interface thread share, under ``lock``."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    loop: asyncio.AbstractEventLoop | None = None
    task: asyncio.Task[None] | None = None
    pending: dict[str, asyncio.Future[dict[str, object]]] = field(default_factory=dict)
    interrupted: bool = False


class SdkRun:
    """One message through the SDK. ``finished`` is called just before the last event
    (``TurnEnded``), once nothing of the message can be asked any more."""

    def __init__(
        self,
        request: RunRequest,
        on_event: Callable[[RunEvent], None],
        *,
        cli_path: str | None,
        finished: Callable[[], None] = lambda: None,
        client_factory: ClientFactory = _default_client,
    ) -> None:
        self._request = request
        self._on_event = on_event
        self._cli_path = cli_path
        self._finished = finished
        self._client_factory = client_factory
        self._state = _State()
        self._stderr: list[str] = []
        self._diagnostics: list[str] = []

    def start(self) -> None:
        """Send the message in a thread of its own; raises ``RunnerError`` if the options cannot
        be made (the events then never come)."""
        options = sdk_options(
            self._request,
            cli_path=self._cli_path,
            can_use_tool=self._can_use_tool,
            stderr=self._stderr.append,
        )
        threading.Thread(target=asyncio.run, args=(self._main(options),), daemon=True).start()

    def answer(self, request_id: str, decision: dict[str, object]) -> None:
        """The answer of the user to the permission question ``request_id`` (the same body as for
        the CLI: ``behavior`` allow with ``updatedInput``, or deny with ``message``)."""
        with self._state.lock:
            future, loop = self._state.pending.pop(request_id, None), self._state.loop
        if future is None or loop is None:
            raise RunnerError("Claude is no longer waiting for this answer.")
        loop.call_soon_threadsafe(_settle, future, decision)

    def interrupt(self) -> None:
        """Stop the message: it is cancelled, which closes the CLI."""
        with self._state.lock:
            self._state.interrupted = True
            task, loop = self._state.task, self._state.loop
        if task is not None and loop is not None:
            loop.call_soon_threadsafe(task.cancel)

    # -- the thread of the message ------------------------------------------------------------

    async def _main(self, options: ClaudeAgentOptions) -> None:
        with self._state.lock:
            self._state.loop = asyncio.get_running_loop()
            self._state.task = asyncio.current_task()
            interrupted = self._state.interrupted
        exit_code: int | None = 0
        try:
            if not interrupted:
                exit_code = await self._exchange(options)
        except asyncio.CancelledError:
            exit_code = None
        with self._state.lock:
            self._state.pending.clear()
            interrupted = self._state.interrupted
        self._finished()
        stderr = "".join(line if line.endswith("\n") else f"{line}\n" for line in self._stderr)
        self._on_event(TurnEnded(exit_code, interrupted, stderr.strip(), self._diagnostics))

    async def _exchange(self, options: ClaudeAgentOptions) -> int | None:
        """Send the prompt and hand on the events until the result; the exit code (1 when the SDK
        failed, which is then in the diagnostics)."""
        from claude_agent_sdk import ClaudeSDKError  # noqa: PLC0415 (the SDK is optional)

        from wxclaude.core.claude.sdk_messages import events_of  # noqa: PLC0415 (imports the SDK)

        client = self._client_factory(options)
        try:
            await client.connect()
            await client.query(self._request.prompt)
            async for message in client.receive_response():
                for event in events_of(message):
                    self._on_event(event)
        except ClaudeSDKError as error:
            self._diagnostics.append(str(error))
            return getattr(error, "exit_code", None) or 1
        finally:
            await _disconnect(client, self._diagnostics)
        return 0

    async def _can_use_tool(
        self, tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResult:
        """A permission question of the CLI: it goes to the interface, then waits for
        ``answer``."""
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny  # noqa: PLC0415

        request = PermissionRequest(
            request_id=uuid.uuid4().hex,
            tool_name=tool_name,
            tool_use_id=context.tool_use_id or "",
            input=dict(tool_input),
            description=context.description or "",
            blocked_path=context.blocked_path or "",
            suggested_rule=suggested_rule([update.to_dict() for update in context.suggestions]),
        )
        future: asyncio.Future[dict[str, object]] = asyncio.get_running_loop().create_future()
        with self._state.lock:
            self._state.pending[request.request_id] = future
        self._on_event(request)
        decision = await future
        if decision.get("behavior") == "allow":
            updated = decision.get("updatedInput")
            return PermissionResultAllow(
                updated_input=cast(dict[str, Any], updated) if isinstance(updated, dict) else None
            )
        return PermissionResultDeny(message=str(decision.get("message") or ""))


def _settle(future: asyncio.Future[dict[str, object]], decision: dict[str, object]) -> None:
    if not future.done():
        future.set_result(decision)


async def _disconnect(client: ClaudeSDKClient, diagnostics: list[str]) -> None:
    """Close the CLI; what goes wrong then is only noted (the message is over anyway)."""
    from claude_agent_sdk import ClaudeSDKError  # noqa: PLC0415 (the SDK is optional)

    try:
        await asyncio.shield(client.disconnect())
    except (ClaudeSDKError, OSError) as error:
        diagnostics.append(str(error))
