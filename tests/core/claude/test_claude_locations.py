"""Finding Claude Code in the folders of the Claude application (fake folders)."""

import os
from pathlib import Path

import pytest

from wxclaude.core.claude import runner
from wxclaude.core.claude.claude_locations import installed_claude

pytestmark = pytest.mark.unit

PROGRAM = "claude.exe" if os.name == "nt" else "claude"


def copy(root: Path, profile: str, version: str, build: str, mtime: float = 1000.0) -> Path:
    path = root / profile / "claude-code" / version / build / PROGRAM
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_the_most_recent_version_of_any_application_folder_is_taken(tmp_path: Path) -> None:
    roaming, local = tmp_path / "Roaming", tmp_path / "Local"
    copy(local, "Claude-3p", "2.1.317", "a33a", mtime=5000)
    newest = copy(roaming, "Claude-Compte2", "2.1.321", "d020", mtime=2000)
    copy(roaming, "Claude-Compte2", "2.1.321", "aaaa", mtime=1000)
    copy(roaming, "Claude", "2.1.99", "b", mtime=9000)  # 99 < 317: compared as numbers
    assert installed_claude([roaming, local], tmp_path / "home") == str(newest)


def test_the_native_installer_comes_after(tmp_path: Path) -> None:
    home = tmp_path / "home"
    assert installed_claude([tmp_path], home) is None
    native = home / ".local" / "bin" / PROGRAM
    native.parent.mkdir(parents=True)
    native.write_text("", encoding="utf-8")
    assert installed_claude([tmp_path], home) == str(native)
    newest = copy(tmp_path, "Claude", "2.1.1", "x")
    assert installed_claude([tmp_path], home) == str(newest)


def test_the_path_comes_first_then_the_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = copy(tmp_path, "Claude", "2.1.1", "x")
    monkeypatch.setattr(runner, "installed_claude", lambda: str(found))
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert runner.find_claude() == [str(found)]
    monkeypatch.setattr("shutil.which", lambda _name: "C:/bin/claude.exe")
    assert runner.find_claude() == ["C:/bin/claude.exe"]
