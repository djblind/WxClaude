"""Loading the model of a message on a local server before the message is sent
(``docs/providers.md``, "Model loading").

A local server holds its models in the memory of the computer, which rarely has room for two big
ones. A provider can name a method that WxClaude uses before each of its messages: if the model of
the message is not loaded, the method looks whether there is room for it next to the models that
are; if not, it unloads them first; then it loads it. This replaces the scripts that had to be run
before starting WxClaude, one per model.

The only method for now is LM Studio, through its own API (``/api/v1/models``, ``load``,
``unload``). The memory a model needs is the estimate of its command ``lms`` (``load
--estimate-only``); the memory free is the memory of the computer that Windows says is available
plus the free memory of the NVIDIA cards (``nvidia-smi``). When either cannot be known, the other
models are unloaded: that is what the scripts always did. Everything here runs away from the window
thread (it can take minutes) and never imports ``wx``.
"""

import ctypes
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import ClassVar

from wxclaude.core.config.provider_methods import Opener, default_open, origin_of
from wxclaude.core.errors import ModelLoadError
from wxclaude.i18n import N_, _

NONE = "none"  # the identifier of "no method"
LMSTUDIO = "lmstudio"
UNLOADING = "unload"  # the steps told while a model is prepared
LOADING = "load"
LIST_TIMEOUT_SECONDS = 15.0
LOAD_TIMEOUT_SECONDS = 900.0  # a big model read from the disk takes minutes
_COMMAND_TIMEOUT_SECONDS = 120.0
_MAX_ANSWER_BYTES = 2_000_000
_MAX_DETAIL = 200
_NOT_FOUND = 404
_GIB = 1024**3
_ESTIMATE = re.compile(r"Estimated Total Memory:\s*([\d.,]+)\s*(GiB|GB|MiB|MB)", re.IGNORECASE)
_UNITS = {"gib": _GIB, "gb": 10**9, "mib": 1024**2, "mb": 10**6}

#: Told before each step: the step (``UNLOADING`` or ``LOADING``) and the models it is about.
type Report = Callable[[str, list[str]], None]


@dataclass(frozen=True, slots=True)
class LoadedModel:
    """A model held by the server: its key, the identifier of the loaded copy, and its context."""

    key: str
    instance_id: str
    context_length: int | None = None


class LoadingMethod(ABC):
    """A way to make sure the model of a message is loaded. ``label`` is a message id."""

    id: ClassVar[str]
    label: ClassVar[str]
    active: ClassVar[bool] = True  # False: nothing is done before a message

    @abstractmethod
    def prepare(
        self, base_url: str, model: str, context_length: int | None, report: Report
    ) -> None:
        """Make sure ``model`` is loaded on the server at ``base_url`` (with ``context_length``
        tokens of context when it is given), unloading what must be. Raises ``ModelLoadError``
        with a message for the user."""


class NoLoading(LoadingMethod):
    """The server loads its models by itself, or the user does."""

    id = NONE
    label = N_("No method")
    active = False

    def prepare(
        self, base_url: str, model: str, context_length: int | None, report: Report
    ) -> None:
        return


# -- what the computer has ------------------------------------------------------------------------


def _run(arguments: list[str], timeout: float = _COMMAND_TIMEOUT_SECONDS) -> str | None:
    """The output of a command, both streams (``lms`` writes its estimate to the error stream),
    None if it cannot be run or fails."""
    try:
        done = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError, subprocess.SubprocessError:
        return None
    return done.stdout + done.stderr if done.returncode == 0 else None


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


def available_memory() -> int | None:
    """The bytes of memory free for a model: what Windows says is available (the cache it can
    drop included) plus what the NVIDIA cards have free. None when Windows cannot tell."""
    if sys.platform != "win32":
        return None
    status = _MemoryStatus()
    status.length = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.available_physical) + _free_video_memory()


def _free_video_memory() -> int:
    """The bytes free on the NVIDIA cards; 0 without one (or without ``nvidia-smi``)."""
    output = _run(
        ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        timeout=LIST_TIMEOUT_SECONDS,
    )
    total = 0
    for line in (output or "").splitlines():
        if line.strip().isdigit():
            total += int(line.strip()) * 1024**2
    return total


def lms_command() -> str | None:
    """The command ``lms`` of LM Studio: in the PATH, else where LM Studio puts it."""
    found = shutil.which("lms")
    if found:
        return found
    name = "lms.exe" if sys.platform == "win32" else "lms"
    candidate = Path.home() / ".lmstudio" / "bin" / name
    return str(candidate) if candidate.is_file() else None


def parse_estimate(output: str) -> int | None:
    """The bytes of the line *Estimated Total Memory* of ``lms load --estimate-only``."""
    match = _ESTIMATE.search(output)
    if match is None:
        return None
    try:
        value = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    return int(value * _UNITS[match.group(2).lower()])


def lms_estimate(model: str, context_length: int | None) -> int | None:
    """The bytes LM Studio thinks ``model`` needs; None when it cannot say."""
    command = lms_command()
    if command is None:
        return None
    arguments = [command, "load", model, "--estimate-only", "--parallel", "1"]
    if context_length:
        arguments += ["--context-length", str(context_length)]
    output = _run(arguments)
    return None if output is None else parse_estimate(output)


def start_lms_server() -> bool:
    """Start the server of LM Studio with ``lms server start``; False if that cannot be done."""
    command = lms_command()
    return command is not None and _run([command, "server", "start"]) is not None


# -- LM Studio ------------------------------------------------------------------------------------


def _detail(error: urllib.error.HTTPError) -> str:
    """The message LM Studio gave with an error, short; or ''."""
    try:
        data = json.loads(error.read(_MAX_ANSWER_BYTES).decode("utf-8"))
    except OSError, ValueError:
        return ""
    node = data.get("error") if isinstance(data, dict) else None
    message = node.get("message") if isinstance(node, dict) else node
    return message.strip()[:_MAX_DETAIL] if isinstance(message, str) else ""


def _loaded_models(data: object) -> list[LoadedModel]:
    """The loaded language models of an answer of ``GET /api/v1/models``."""
    entries = data.get("models") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ModelLoadError(_("LM Studio did not answer with its list of models."))
    loaded: list[LoadedModel] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "llm":
            continue
        key, instances = entry.get("key"), entry.get("loaded_instances")
        if not isinstance(key, str) or not isinstance(instances, list):
            continue
        for instance in instances:
            identifier = instance.get("id") if isinstance(instance, dict) else None
            if not isinstance(identifier, str):
                continue
            config = instance.get("config")
            context = config.get("context_length") if isinstance(config, dict) else None
            loaded.append(LoadedModel(key, identifier, context if type(context) is int else None))
    return loaded


class LmStudioLoading(LoadingMethod):
    """LM Studio (0.4 and later): its API loads and unloads the models.

    What reaches the computer (the memory, the estimate, the start of the server) is given to the
    constructor, so that the tests use fakes.
    """

    id = LMSTUDIO
    label = N_("LM Studio")

    def __init__(
        self,
        opener: Opener = default_open,
        memory: Callable[[], int | None] = available_memory,
        estimate: Callable[[str, int | None], int | None] = lms_estimate,
        start_server: Callable[[], bool] = start_lms_server,
    ) -> None:
        self._open = opener
        self._memory = memory
        self._estimate = estimate
        self._start_server = start_server

    def prepare(
        self, base_url: str, model: str, context_length: int | None, report: Report
    ) -> None:
        origin = origin_of(base_url)
        loaded = self.loaded(origin)
        same = [entry for entry in loaded if model in (entry.key, entry.instance_id)]
        if any(context_length in (None, entry.context_length) for entry in same):
            return  # already there, as it is wanted
        if same:  # loaded with another context: loaded again
            report(UNLOADING, [entry.key for entry in same])
            self._unload_all(origin, same)
        others = [entry for entry in loaded if entry not in same]
        if others and not self._fits(model, context_length):
            report(UNLOADING, [entry.key for entry in others])
            self._unload_all(origin, others)
        report(LOADING, [model])
        body: dict[str, object] = {"model": model, "parallel": 1}
        if context_length:
            body["context_length"] = context_length
        self._call(origin, "/api/v1/models/load", body, LOAD_TIMEOUT_SECONDS, model)

    def loaded(self, origin: str) -> list[LoadedModel]:
        """The models LM Studio holds; its server is started once if it does not answer."""
        try:
            data = self._call(origin, "/api/v1/models", None, LIST_TIMEOUT_SECONDS, "")
        except ModelLoadError as error:
            cause = error.__cause__
            unreachable = isinstance(cause, urllib.error.URLError) and not isinstance(
                cause, urllib.error.HTTPError
            )
            if not unreachable or not self._start_server():
                raise
            data = self._call(origin, "/api/v1/models", None, LIST_TIMEOUT_SECONDS, "")
        return _loaded_models(data)

    # -- inside ---------------------------------------------------------------------------

    def _fits(self, model: str, context_length: int | None) -> bool:
        """Is there room for ``model`` next to what is loaded? No when it cannot be known."""
        needed = self._estimate(model, context_length)
        free = self._memory()
        return needed is not None and free is not None and needed <= free

    def _unload_all(self, origin: str, models: list[LoadedModel]) -> None:
        for entry in models:
            body: dict[str, object] = {"instance_id": entry.instance_id}
            self._call(origin, "/api/v1/models/unload", body, LIST_TIMEOUT_SECONDS, entry.key)

    def _call(
        self, origin: str, path: str, body: dict[str, object] | None, timeout: float, model: str
    ) -> object:
        """The JSON answer of LM Studio to a GET (no ``body``) or a POST. Raises
        ``ModelLoadError``; the error of the connection is its cause."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            origin + path,
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with self._open(request, timeout) as response:
                answer = response.read(_MAX_ANSWER_BYTES)
        except urllib.error.HTTPError as error:
            raise ModelLoadError(self._refusal(error, path, model)) from error
        except urllib.error.URLError as error:
            raise ModelLoadError(
                _("LM Studio does not answer at {address}. Start its server.").format(
                    address=origin
                )
            ) from error
        except (HTTPException, OSError) as error:
            raise ModelLoadError(
                _("LM Studio stopped answering: {reason}").format(reason=error)
            ) from error
        try:
            return json.loads(answer.decode("utf-8"))
        except UnicodeDecodeError, json.JSONDecodeError:
            raise ModelLoadError(_("LM Studio gave an answer that is not understood.")) from None

    @staticmethod
    def _refusal(error: urllib.error.HTTPError, path: str, model: str) -> str:
        detail = _detail(error)
        if error.code == _NOT_FOUND and path == "/api/v1/models":
            return _(
                "This server cannot load models (error 404): it is not LM Studio, or a version "
                "older than 0.4."
            )
        if error.code == _NOT_FOUND:
            return _("LM Studio has no model {model}. Check its name in the provider.").format(
                model=model
            )
        if path.endswith("/unload"):
            return _("LM Studio could not unload {model} (error {code}). {detail}").format(
                model=model, code=error.code, detail=detail
            )
        return _("LM Studio could not load {model} (error {code}). {detail}").format(
            model=model, code=error.code, detail=detail
        )


# -- the registry ---------------------------------------------------------------------------------

#: The methods, in the order of the list of the form. A method is added here.
LOADING_METHODS: tuple[LoadingMethod, ...] = (NoLoading(), LmStudioLoading())


def loading_method(identifier: str) -> LoadingMethod:
    """The method named ``identifier``; "no method" when it is not known."""
    return next((m for m in LOADING_METHODS if m.id == identifier), LOADING_METHODS[0])
