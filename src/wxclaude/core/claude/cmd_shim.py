"""The ``claude.cmd`` of an npm install, replaced by the program it starts.

npm puts a small batch file (``claude.cmd``) in the PATH. A batch file is always run by ``cmd.exe``,
which reads the arguments a second time: ``&``, ``|``, ``%`` or quotes in an argument (a
conversation name, the JSON of ``--settings``) are then cut or taken as commands, whatever quoting
Python does. So the program the batch file starts is run directly instead: ``node`` with the script
of the package, or the executable of the package. A batch file that cannot be read this way is
kept as it is.
"""

import re
import shutil
from pathlib import Path

_BATCH_SUFFIXES = frozenset({".cmd", ".bat"})
# The target of an npm shim: "%dp0%\node_modules\...\cli.js" (or %~dp0), always quoted.
_TARGET = re.compile(r'"%~?dp0%?\\([^"%]+\.(?:js|mjs|cjs|exe))"', re.IGNORECASE)
_MAX_SHIM_BYTES = 64 * 1024  # an npm shim is a few hundred bytes


def is_batch(path: str) -> bool:
    """Is ``path`` a batch file, run by ``cmd.exe``?"""
    return Path(path).suffix.lower() in _BATCH_SUFFIXES


def resolve_shim(path: str) -> list[str] | None:
    """The command the npm shim ``path`` stands for, without ``cmd.exe``; None if ``path`` is not
    a batch file whose target can be found (it is then run as it is)."""
    target = _shim_target(Path(path)) if is_batch(path) else None
    if target is None:
        return None
    if target.suffix.lower() == ".exe":
        return [str(target)]
    beside = Path(path).parent / "node.exe"  # what the shim prefers, like npm
    node = str(beside) if beside.is_file() else shutil.which("node")
    return [node, str(target)] if node else None


def _shim_target(shim: Path) -> Path | None:
    """The program or script the batch file ``shim`` starts, if it exists; else None."""
    try:
        if shim.stat().st_size > _MAX_SHIM_BYTES:
            return None
        text = shim.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # The shim also names the node.exe it may run the script with: the target is the other path.
    targets = [name for name in _TARGET.findall(text) if Path(name).name.lower() != "node.exe"]
    target = shim.parent / targets[-1] if targets else None
    return target if target is not None and target.is_file() else None
