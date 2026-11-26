"""The local servers that WxClaude started itself (``docs/providers.md``, "Model loading").

A provider whose loading method is *llama.cpp server* gives the command of its server; WxClaude
starts it when the server does not answer. Such a server holds the memory of the graphics card, so
it is stopped before LM Studio loads a model, before another server starts, and when WxClaude ends.
Only the processes started here are ever stopped: never a server the user started by hand. This
module never imports ``wx``.
"""

import atexit
import shlex
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

_STOP_WAIT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class StartedServer:
    """A server started by WxClaude: the process and the name it is told by (its model)."""

    process: subprocess.Popen[bytes]
    name: str


_started: list[StartedServer] = []
_lock = threading.Lock()


def start_command(command: str) -> subprocess.Popen[bytes]:
    """Start ``command`` in the background, without a window and without its output. Raises
    ``OSError`` if it cannot be started."""
    arguments: str | list[str] = command if sys.platform == "win32" else shlex.split(command)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    return subprocess.Popen(
        arguments,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def remember(process: subprocess.Popen[bytes], name: str) -> None:
    """Keep a server WxClaude started, to stop it later."""
    with _lock:
        _started.append(StartedServer(process, name))


def running_servers() -> list[str]:
    """The names of the servers WxClaude started that still run."""
    with _lock:
        return [server.name for server in _started if server.process.poll() is None]


def stop_servers(report: Callable[[list[str]], None] = lambda names: None) -> list[str]:
    """Stop the servers WxClaude started (``report`` is told their names first, if any run);
    the names of those that ran."""
    with _lock:
        servers = list(_started)
        _started.clear()
    names = [server.name for server in servers if server.process.poll() is None]
    if names:
        report(names)
    for server in servers:
        _stop(server.process)
    return names


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(_STOP_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()


atexit.register(stop_servers)  # a server must not hold the graphics card once WxClaude is gone
