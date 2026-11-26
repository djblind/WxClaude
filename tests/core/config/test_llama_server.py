"""A llama.cpp server started by WxClaude for the model of a message (fakes: no process, no
network)."""

import io
import json
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from wxclaude.core.config import local_servers
from wxclaude.core.config.model_loading import (
    LOADING,
    UNLOADING,
    LlamaServerLoading,
    LmStudioLoading,
)
from wxclaude.core.errors import ModelLoadError

pytestmark = pytest.mark.unit

BASE = "http://127.0.0.1:8080"
LM = "http://localhost:1234"
COMMAND = r'"C:\llama\llama-server.exe" -m model.gguf --port 8080 --alias inkling'


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeProcess:
    def __init__(self, code: int | None = None) -> None:
        self.code = code
        self.terminated = False

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        self.terminated = True
        self.code = 1

    def wait(self, timeout: float | None = None) -> int:
        return self.code or 0

    def kill(self) -> None:
        self.code = -9


class World:
    """The llama.cpp server (up after it was started, or never) and LM Studio."""

    def __init__(self, *, lm_loaded: list[str] | None = None, comes_up: bool = True) -> None:
        self.up = False
        self.comes_up = comes_up
        self.lm_loaded = list(lm_loaded or [])
        self.lm_running = lm_loaded is not None
        self.started: list[str] = []
        self.process = FakeProcess()
        self.steps: list[tuple[str, list[str]]] = []

    def open(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        url = request.full_url
        if url == BASE + "/health":
            if not self.up:
                raise urllib.error.URLError("refused")
            return FakeResponse(b'{"status":"ok"}')
        if not self.lm_running:
            raise urllib.error.URLError("refused")
        if url == LM + "/api/v1/models":
            models = [
                {"type": "llm", "key": key, "loaded_instances": [{"id": key}]}
                for key in self.lm_loaded
            ]
            return FakeResponse(json.dumps({"models": models}).encode())
        if url == LM + "/api/v1/models/unload":
            data = request.data
            assert isinstance(data, bytes)
            self.lm_loaded.remove(json.loads(data)["instance_id"])
            return FakeResponse(b"{}")
        raise AssertionError(url)

    def start(self, command: str) -> FakeProcess:
        self.started.append(command)
        self.up = self.comes_up
        return self.process

    def report(self, action: str, models: list[str]) -> None:
        self.steps.append((action, models))

    def method(self) -> LlamaServerLoading:
        clock = iter(range(0, 100000, 1))
        return LlamaServerLoading(
            self.open,
            LmStudioLoading(self.open, start_server=lambda: False),
            self.start,  # type: ignore[arg-type]
            sleep=lambda seconds: None,
            clock=lambda: float(next(clock)),
        )


@pytest.fixture(autouse=True)
def no_servers() -> Iterator[None]:
    local_servers.stop_servers()
    yield
    local_servers.stop_servers()


def test_a_server_that_answers_is_left_as_it_is() -> None:
    world = World()
    world.up = True
    world.method().prepare(BASE, "inkling", None, world.report, COMMAND)
    assert world.started == []
    assert world.steps == []


def test_lm_studio_is_unloaded_then_the_server_started() -> None:
    world = World(lm_loaded=["qwen-122b"])
    world.method().prepare(BASE, "inkling", None, world.report, COMMAND)
    assert world.lm_loaded == []
    assert world.started == [COMMAND]
    assert world.steps == [(UNLOADING, ["qwen-122b"]), (LOADING, ["inkling"])]
    assert local_servers.running_servers() == ["inkling"]


def test_lm_studio_stops_the_server_before_loading() -> None:
    world = World(lm_loaded=[])
    world.method().prepare(BASE, "inkling", None, world.report, COMMAND)
    steps: list[tuple[str, list[str]]] = []
    lm_studio = LmStudioLoading(world.open, lambda: None, lambda m, c: None, lambda: False)
    with pytest.raises(AssertionError):  # the fake LM Studio has no load: only the stop matters
        lm_studio.prepare(LM, "qwen-27b", None, lambda a, m: steps.append((a, m)))
    assert steps[0] == (UNLOADING, ["inkling"])
    assert world.process.terminated
    assert local_servers.running_servers() == []


def test_without_a_command_or_a_server_it_is_said() -> None:
    world = World()
    with pytest.raises(ModelLoadError, match="no command"):
        world.method().prepare(BASE, "inkling", None, world.report, "  ")


def test_a_server_that_stops_at_once_is_said() -> None:
    world = World(comes_up=False)
    world.process = FakeProcess(code=1)
    with pytest.raises(ModelLoadError, match="exit code 1"):
        world.method().prepare(BASE, "inkling", None, world.report, COMMAND)


def test_a_server_that_never_answers_is_stopped() -> None:
    world = World(comes_up=False)
    with pytest.raises(ModelLoadError, match="in time"):
        world.method().prepare(BASE, "inkling", None, world.report, COMMAND)
    assert world.process.terminated
