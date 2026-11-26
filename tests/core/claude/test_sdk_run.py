"""Sending a message through the Agent SDK, with a fake client of the SDK: no CLI, no network."""

import json
import threading
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, cast

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import ToolPermissionContext

from wxclaude.core.claude.events import (
    AssistantText,
    PermissionRequest,
    RunEvent,
    SessionInit,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.launch import ProviderLaunch
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest
from wxclaude.core.claude.sdk_run import CLIENT_APP, SdkRun, sdk_options
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import ENGINE_SDK, Provider
from wxclaude.core.errors import RunnerError

pytestmark = pytest.mark.unit

SESSION = "11111111-1111-4111-8111-111111111111"
API = Provider(
    id="api",
    name="API",
    base_url="https://api.anthropic.com",
    tiers=["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"],
    engine=ENGINE_SDK,
)
AGENT = Agent(model="claude-haiku-5-5", effort="low", permission_mode="manual", provider="api")


def _request(tmp_path: Path, **changes: Any) -> RunRequest:
    values: dict[str, Any] = {
        "prompt": "Hello",
        "agent": AGENT,
        "session_id": SESSION,
        "resume": False,
        "cwd": tmp_path,
        "provider": ProviderLaunch(API, "sk-ant-test", scrub=True),
    }
    values.update(changes)
    return RunRequest(**values)


def _options(request: RunRequest, inherited: dict[str, str] | None = None) -> ClaudeAgentOptions:
    return sdk_options(
        request,
        cli_path="C:/claude/claude.exe",
        can_use_tool=lambda *_args: None,
        stderr=lambda _line: None,
        inherited=inherited if inherited is not None else {"PATH": "C:/bin"},
    )


# -- the options ------------------------------------------------------------------------------


def test_the_options_are_those_of_claude_code_with_the_key_in_the_environment(
    tmp_path: Path,
) -> None:
    options = _options(_request(tmp_path, name="Notes"))
    assert options.system_prompt == {"type": "preset", "preset": "claude_code"}
    assert (options.model, options.effort, options.permission_mode) == (
        "claude-haiku-5-5",
        "low",
        "manual",
    )
    assert options.session_id == SESSION
    assert options.resume is None
    assert options.cli_path == "C:/claude/claude.exe"
    assert options.cwd == tmp_path
    assert options.extra_args == {"name": "Notes"}
    assert options.client_app == CLIENT_APP
    assert options.setting_sources is None  # every source, as for Claude Code
    assert options.env["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert "ANTHROPIC_AUTH_TOKEN" not in options.env
    assert options.env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "1"
    settings = json.loads(options.settings or "{}")
    assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com"
    assert "sk-ant-test" not in (options.settings or "")


def test_a_resumed_conversation_and_a_branch(tmp_path: Path) -> None:
    resumed = _options(_request(tmp_path, resume=True, name="Notes"))
    assert (resumed.resume, resumed.session_id, resumed.extra_args) == (SESSION, None, {})
    branch = _options(_request(tmp_path, fork_from="parent"))
    assert (branch.resume, branch.fork_session, branch.session_id) == ("parent", True, SESSION)


def test_the_variables_of_wxclaude_that_choose_a_provider_are_given_empty(tmp_path: Path) -> None:
    inherited = {"PATH": "C:/bin", "ANTHROPIC_BASE_URL": "http://localhost:1234"}
    options = _options(_request(tmp_path), inherited)
    assert options.env["ANTHROPIC_BASE_URL"] == ""  # the SDK adds its env to that of WxClaude
    assert "PATH" not in options.env  # unchanged: the SDK takes it from WxClaude


def test_the_name_of_the_caller_is_left_to_the_sdk(tmp_path: Path) -> None:
    """Measured: WxClaude started from the Claude application inherits the name claude-desktop;
    given back to the SDK, the API took the message for Claude Code and refused the credits."""
    inherited = {"PATH": "C:/bin", "CLAUDE_CODE_ENTRYPOINT": "claude-desktop"}
    options = _options(_request(tmp_path), inherited)
    assert "CLAUDE_CODE_ENTRYPOINT" not in options.env


def test_a_restricted_folder_reads_only_the_settings_of_the_user(tmp_path: Path) -> None:
    agent = Agent(model="claude-haiku-5-5", effort="low", permission_mode="auto", provider="api")
    options = _options(_request(tmp_path, restricted=True, agent=agent))
    assert options.setting_sources == ["user"]
    assert str(options.permission_mode) == "manual"


def test_the_effort_is_left_out_when_the_provider_does_not_take_it(tmp_path: Path) -> None:
    provider = Provider(
        id="api",
        name="API",
        base_url="https://x",
        tiers=["m"],
        engine=ENGINE_SDK,
        send_effort=False,
    )
    options = _options(_request(tmp_path, provider=ProviderLaunch(provider, "k")))
    assert options.effort is None


def test_an_incomplete_agent_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RunnerError):
        _options(_request(tmp_path, agent=Agent(model="", effort="low", permission_mode="manual")))


# -- a message --------------------------------------------------------------------------------


def _result(*, is_error: bool = False, text: str = "Done") -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=120,
        duration_api_ms=100,
        is_error=is_error,
        num_turns=1,
        session_id=SESSION,
        total_cost_usd=0.002,
        usage={"input_tokens": 10, "output_tokens": 5},
        result=text,
    )


class FakeClient:
    """Plays a list of steps: an SDK message, or a permission question asked of WxClaude."""

    def __init__(self, options: ClaudeAgentOptions, steps: list[object]) -> None:
        self.options = options
        self.steps = steps
        self.prompts: list[str] = []
        self.decisions: list[object] = []
        self.disconnected = False
        self.release = threading.Event()

    async def connect(self) -> None:
        return None

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)

    async def receive_response(self) -> AsyncIterator[object]:
        for step in self.steps:
            if step == "ask":
                assert self.options.can_use_tool is not None
                context = ToolPermissionContext(tool_use_id="t1", description="Run ls")
                decision = await self.options.can_use_tool("Bash", {"command": "ls"}, context)
                self.decisions.append(decision)
            elif step == "hang":
                import asyncio  # noqa: PLC0415

                await asyncio.sleep(30)
            else:
                yield step

    async def disconnect(self) -> None:
        self.disconnected = True


class Collector:
    def __init__(self) -> None:
        self.events: list[RunEvent] = []
        self.done = threading.Event()
        self.on_request: Callable[[PermissionRequest], None] = lambda _request: None

    def __call__(self, event: RunEvent) -> None:
        self.events.append(event)
        if isinstance(event, PermissionRequest):
            self.on_request(event)
        if isinstance(event, TurnEnded):
            self.done.set()

    @property
    def ended(self) -> TurnEnded:
        assert self.done.wait(10), "the message did not end"
        last = self.events[-1]
        assert isinstance(last, TurnEnded)
        return last


def _run(
    tmp_path: Path, steps: list[object], collector: Collector
) -> tuple[SdkRun, list[FakeClient]]:
    clients: list[FakeClient] = []

    def factory(options: ClaudeAgentOptions) -> Any:
        clients.append(FakeClient(options, steps))
        return clients[-1]

    run = SdkRun(_request(tmp_path), collector, cli_path=None, client_factory=factory)
    return run, clients


def test_the_messages_of_the_sdk_become_the_events_of_the_cli(tmp_path: Path) -> None:
    steps: list[object] = [
        SystemMessage("init", {"session_id": SESSION, "model": "claude-haiku-5-5"}),
        AssistantMessage(
            [TextBlock("Hi"), ToolUseBlock("t1", "Read", {"file_path": "a.txt"})], "m"
        ),
        _result(),
    ]
    collector = Collector()
    run, clients = _run(tmp_path, steps, collector)
    run.start()
    ended = collector.ended
    kinds = [type(event) for event in collector.events]
    assert kinds == [SessionInit, AssistantText, ToolUsed, TurnResult, TurnEnded]
    result = collector.events[3]
    assert isinstance(result, TurnResult)
    assert (result.text, result.cost_usd, result.usage is not None) == ("Done", 0.002, True)
    assert (ended.exit_code, ended.interrupted) == (0, False)
    assert clients[0].prompts == ["Hello"]
    assert clients[0].disconnected


def test_a_permission_is_asked_of_the_interface_and_its_answer_goes_back(tmp_path: Path) -> None:
    collector = Collector()
    run, clients = _run(tmp_path, ["ask", "ask", _result()], collector)
    answers = iter(
        [
            {"behavior": "allow", "updatedInput": {"command": "ls -a"}},
            {"behavior": "deny", "message": "Not now"},
        ]
    )
    collector.on_request = lambda request: threading.Thread(
        target=run.answer, args=(request.request_id, next(answers))
    ).start()
    run.start()
    assert collector.ended.exit_code == 0
    first, second = clients[0].decisions
    assert isinstance(first, PermissionResultAllow)
    assert first.updated_input == {"command": "ls -a"}
    assert isinstance(second, PermissionResultDeny)
    assert second.message == "Not now"
    request = next(e for e in collector.events if isinstance(e, PermissionRequest))
    assert (request.tool_name, request.tool_use_id, request.description) == ("Bash", "t1", "Run ls")


def test_an_answer_to_a_question_that_is_not_asked_is_refused(tmp_path: Path) -> None:
    run, _clients = _run(tmp_path, [_result()], Collector())
    with pytest.raises(RunnerError):
        run.answer("nothing", {"behavior": "allow"})


def test_interrupting_ends_the_message_and_closes_the_cli(tmp_path: Path) -> None:
    collector = Collector()
    run, clients = _run(tmp_path, ["hang"], collector)
    run.start()
    while not clients:
        threading.Event().wait(0.01)
    threading.Event().wait(0.1)  # the message waits in the fake CLI
    run.interrupt()
    ended = collector.ended
    assert ended.interrupted
    assert ended.exit_code is None
    assert clients[0].disconnected


def test_a_failure_of_the_sdk_is_a_diagnostic_and_an_exit_code(tmp_path: Path) -> None:
    from claude_agent_sdk import CLIConnectionError  # noqa: PLC0415

    class Broken(FakeClient):
        async def connect(self) -> None:
            raise CLIConnectionError("cannot start claude")

    collector = Collector()
    run = SdkRun(
        _request(tmp_path),
        collector,
        cli_path=None,
        client_factory=lambda o: cast(Any, Broken(o, [])),
    )
    run.start()
    ended = collector.ended
    assert ended.exit_code == 1
    assert ended.diagnostics == ["cannot start claude"]


# -- through the runner -----------------------------------------------------------------------


def test_the_runner_sends_a_provider_of_the_sdk_through_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[SdkRun] = []
    monkeypatch.setattr(SdkRun, "start", lambda self: started.append(self))
    runner = ClaudeRunner(["C:/claude/claude.exe"])
    runner.start(_request(tmp_path), lambda _event: None)
    assert len(started) == 1
    assert runner.is_running
    with pytest.raises(RunnerError):  # one message at a time, whatever the engine
        runner.start(_request(tmp_path), lambda _event: None)
    assert started[0]._cli_path == "C:/claude/claude.exe"
