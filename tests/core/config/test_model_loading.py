"""Loading the model of a message on LM Studio (a fake server, no network, no ``lms``)."""

import io
import json
import urllib.error
import urllib.request

import pytest

from wxclaude.core.config.model_loading import (
    LOADING,
    LOADING_METHODS,
    NONE,
    UNLOADING,
    LmStudioLoading,
    NoLoading,
    loading_method,
    parse_estimate,
)
from wxclaude.core.errors import ModelLoadError

pytestmark = pytest.mark.unit

BASE = "http://localhost:1234"
GIB = 1024**3


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def http_error(code: int, message: str = "") -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message}}).encode() if message else b""
    return urllib.error.HTTPError("http://x", code, "msg", {}, io.BytesIO(body))  # type: ignore[arg-type]


class FakeLmStudio:
    """Holds loaded models and answers as LM Studio does; records what it is asked."""

    def __init__(self, loaded: dict[str, int] | None = None) -> None:
        self.loaded = dict(loaded or {})  # model key -> context length
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.down = False  # the server does not answer
        self.refuse_load: urllib.error.HTTPError | None = None

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        if self.down:
            raise urllib.error.URLError("connection refused")
        path = request.full_url.removeprefix(BASE)
        data = request.data
        body = json.loads(data) if isinstance(data, bytes) else None
        self.calls.append((path, body))
        if path == "/api/v1/models":
            return self._answer({"models": self._models()})
        assert body is not None
        if path == "/api/v1/models/unload":
            del self.loaded[str(body["instance_id"])]
            return self._answer({"instance_id": body["instance_id"]})
        if self.refuse_load is not None:
            raise self.refuse_load
        context = body.get("context_length", 4096)
        assert isinstance(context, int)
        self.loaded[str(body["model"])] = context
        return self._answer({"status": "loaded"})

    def _models(self) -> list[dict[str, object]]:
        keys = ["small", "big", *self.loaded]
        models: list[dict[str, object]] = [
            {
                "type": "llm",
                "key": key,
                "loaded_instances": (
                    [{"id": key, "config": {"context_length": self.loaded[key]}}]
                    if key in self.loaded
                    else []
                ),
            }
            for key in dict.fromkeys(keys)
        ]
        models.append({"type": "embedding", "key": "embed", "loaded_instances": [{"id": "embed"}]})
        return models

    @staticmethod
    def _answer(data: object) -> FakeResponse:
        return FakeResponse(json.dumps(data).encode())

    @property
    def paths(self) -> list[str]:
        return [path for path, _body in self.calls]


class Steps:
    def __init__(self) -> None:
        self.said: list[tuple[str, list[str]]] = []

    def __call__(self, action: str, models: list[str]) -> None:
        self.said.append((action, models))


def method(
    server: FakeLmStudio, *, free: int | None = 100 * GIB, needed: int | None = 20 * GIB
) -> LmStudioLoading:
    return LmStudioLoading(server, lambda: free, lambda model, context: needed, lambda: False)


def test_a_model_already_loaded_is_left_as_it_is() -> None:
    server = FakeLmStudio({"big": 131072})
    steps = Steps()
    method(server).prepare(BASE, "big", 131072, steps)
    assert server.paths == ["/api/v1/models"]
    assert steps.said == []


def test_without_a_context_any_loaded_copy_will_do() -> None:
    server = FakeLmStudio({"big": 8192})
    method(server).prepare(BASE, "big", None, Steps())
    assert server.paths == ["/api/v1/models"]


def test_a_model_is_loaded_next_to_another_when_there_is_room() -> None:
    server = FakeLmStudio({"small": 4096})
    steps = Steps()
    method(server, free=50 * GIB, needed=40 * GIB).prepare(BASE, "big", 131072, steps)
    assert server.loaded == {"small": 4096, "big": 131072}
    assert steps.said == [(LOADING, ["big"])]
    assert server.calls[-1] == (
        "/api/v1/models/load",
        {"model": "big", "parallel": 1, "context_length": 131072},
    )


def test_the_other_models_are_unloaded_when_there_is_no_room() -> None:
    server = FakeLmStudio({"small": 4096})
    steps = Steps()
    method(server, free=30 * GIB, needed=40 * GIB).prepare(BASE, "big", None, steps)
    assert server.loaded == {"big": 4096}
    assert steps.said == [(UNLOADING, ["small"]), (LOADING, ["big"])]
    assert ("/api/v1/models/load", {"model": "big", "parallel": 1}) in server.calls


@pytest.mark.parametrize(("free", "needed"), [(None, 1), (100 * GIB, None)])
def test_what_cannot_be_measured_unloads_the_others(free: int | None, needed: int | None) -> None:
    server = FakeLmStudio({"small": 4096})
    method(server, free=free, needed=needed).prepare(BASE, "big", None, Steps())
    assert server.loaded == {"big": 4096}


def test_a_model_loaded_with_another_context_is_loaded_again() -> None:
    server = FakeLmStudio({"big": 8192})
    steps = Steps()
    method(server).prepare(BASE, "big", 131072, steps)
    assert server.loaded == {"big": 131072}
    assert steps.said == [(UNLOADING, ["big"]), (LOADING, ["big"])]


def test_nothing_is_unloaded_when_nothing_is_loaded() -> None:
    server = FakeLmStudio()
    steps = Steps()
    method(server, free=None).prepare(BASE, "big", None, steps)
    assert steps.said == [(LOADING, ["big"])]


def test_a_server_that_does_not_answer_is_started_once() -> None:
    server = FakeLmStudio()
    server.down = True
    started: list[bool] = []

    def start() -> bool:
        started.append(True)
        server.down = False
        return True

    LmStudioLoading(server, lambda: None, lambda m, c: None, start).prepare(
        BASE, "big", None, Steps()
    )
    assert started == [True]
    assert server.loaded == {"big": 4096}


def test_a_server_that_cannot_be_started_is_said() -> None:
    server = FakeLmStudio()
    server.down = True
    with pytest.raises(ModelLoadError, match="does not answer at http://localhost:1234"):
        method(server).prepare(BASE + "/v1", "big", None, Steps())


def test_an_unknown_model_and_a_refused_load_are_said() -> None:
    server = FakeLmStudio()
    server.refuse_load = http_error(404, "Model x not found")
    with pytest.raises(ModelLoadError, match="no model big"):
        method(server).prepare(BASE, "big", None, Steps())
    server.refuse_load = http_error(500, "Not enough memory")
    with pytest.raises(ModelLoadError, match=r"could not load big \(error 500\)\. Not enough"):
        method(server).prepare(BASE, "big", None, Steps())


def test_a_server_without_the_api_of_lm_studio_is_said() -> None:
    def old(request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise http_error(404)

    with pytest.raises(ModelLoadError, match=r"older than 0\.4"):
        method(old).prepare(BASE, "big", None, Steps())  # type: ignore[arg-type]


def test_the_estimate_of_lms_is_read() -> None:
    output = "Model: big\nEstimated GPU Memory:   77.95 GiB\nEstimated Total Memory: 77.95 GiB\n"
    assert parse_estimate(output) == int(77.95 * GIB)
    assert parse_estimate("Estimated Total Memory: 512,5 MiB") == int(512.5 * 1024**2)
    assert parse_estimate("nothing") is None


def test_the_registry() -> None:
    assert [m.id for m in LOADING_METHODS] == [NONE, "lmstudio"]
    assert isinstance(loading_method("unknown"), NoLoading)
    assert not loading_method(NONE).active
    assert isinstance(loading_method("lmstudio"), LmStudioLoading)
