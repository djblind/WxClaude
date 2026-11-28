"""Following a file that grows, such as the log of a long work that runs without Claude
(``docs/interface.md``, "Following a file"): the lines added since the last look, and only whole
lines (a line still being written waits for its end). Nothing here touches ``wx``.
"""

from dataclasses import dataclass, field
from pathlib import Path

#: The last lines shown when the following starts, so that the user knows where the work is.
LINES_AT_START = 5
_LONGEST_READ = 1_000_000  # bytes read at once: a file that grew by more is read in steps
_BOM = "﻿"


@dataclass(slots=True)
class FileFollower:
    """The new lines of ``path``, one look after the other. A file that is emptied or replaced by
    a shorter one is read again from its start; a file that does not exist (yet, or any more) gives
    no line."""

    path: Path
    _offset: int = 0
    _pending: bytes = b""
    _started: bool = field(default=False)

    def new_lines(self) -> list[str]:
        """The whole lines added since the last call. The first call gives the last
        ``LINES_AT_START`` lines of the file."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self._offset:  # emptied or replaced
            self._offset, self._pending = 0, b""
        if not self._started:
            self._started = True
            return self._read_all()[-LINES_AT_START:]
        return self._read_all()

    def _read_all(self) -> list[str]:
        lines: list[str] = []
        while True:
            chunk = self._read_chunk()
            if not chunk:
                return lines
            lines.extend(self._split(chunk))

    def _read_chunk(self) -> bytes:
        try:
            with self.path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read(_LONGEST_READ)
        except OSError:
            return b""
        self._offset += len(chunk)
        return chunk

    def _split(self, chunk: bytes) -> list[str]:
        """Whole lines of what was read; the end of an unfinished line waits for the next read."""
        data = self._pending + chunk
        *whole, self._pending = data.split(b"\n")
        texts = [line.decode("utf-8", errors="replace").rstrip("\r") for line in whole]
        return [text.lstrip(_BOM) for text in texts if text.strip(_BOM + " \t")]
