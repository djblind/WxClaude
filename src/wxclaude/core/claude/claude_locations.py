"""Where Claude Code is installed when it is not in the PATH (``docs/interface.md``, Preferences).

The Claude application for Windows keeps its own copy of Claude Code in the folder of its data:
``<data>\\claude-code\\<version>\\<build>\\claude.exe``, the folder of the data being in
``%APPDATA%`` or ``%LOCALAPPDATA%`` (``Claude``, ``Claude-3p``, or the folder given to
``--user-data-dir`` for a second account). Nothing puts it in the PATH. The native installer of
Claude Code puts it in ``~\\.local\\bin``. When ``claude`` is not in the PATH, the most recent copy
found in those places is used: it is the same program whatever the account of the application, and
the account Claude Code uses is the one it signed in with itself (*Sign in to Claude*), not the one
of the application. This module never imports ``wx``.
"""

import os
import sys
from pathlib import Path

_PROGRAM = "claude.exe" if sys.platform == "win32" else "claude"
_FOLDER = "claude-code"  # the folder of the copies, in the data of the application


def _version(text: str) -> tuple[int, ...]:
    """``2.1.321`` as numbers to compare; () when it is not a version."""
    parts = text.split(".")
    return tuple(int(part) for part in parts) if all(part.isdigit() for part in parts) else ()


def search_roots() -> list[Path]:
    """The folders whose sub-folders may hold the data of a Claude application."""
    roots = [Path(value) for name in ("APPDATA", "LOCALAPPDATA") if (value := os.environ.get(name))]
    return [root for root in roots if root.is_dir()]


def _copies(roots: list[Path]) -> list[Path]:
    """Every ``claude-code\\<version>\\<build>\\claude.exe`` one level under the roots."""
    found: list[Path] = []
    for root in roots:
        try:
            folders = [entry / _FOLDER for entry in root.iterdir() if entry.is_dir()]
        except OSError:
            continue
        for folder in folders:
            try:
                found += [path for path in folder.glob(f"*/*/{_PROGRAM}") if path.is_file()]
            except OSError:
                continue
    return found


def _modified(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def installed_claude(roots: list[Path] | None = None, home: Path | None = None) -> str | None:
    """The most recent Claude Code of the Claude applications (by version, then by date), else
    the one of the native installer; None when there is none."""
    copies = _copies(search_roots() if roots is None else roots)
    if copies:
        newest = max(copies, key=lambda path: (_version(path.parent.parent.name), _modified(path)))
        return str(newest)
    native = (Path.home() if home is None else home) / ".local" / "bin" / _PROGRAM
    return str(native) if native.is_file() else None
