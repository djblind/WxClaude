"""The ``claude.cmd`` of npm, replaced by the program it starts."""

from pathlib import Path

import pytest

from wxclaude.core.claude.cmd_shim import is_batch, resolve_shim
from wxclaude.core.claude.runner import find_claude

pytestmark = pytest.mark.unit

# What npm writes (cmd-shim), shortened to the line that starts the program.
NODE_SHIM = (
    "@ECHO off\r\n"
    'IF EXIST "%dp0%\\node.exe" (SET "_prog=%dp0%\\node.exe") ELSE (SET "_prog=node")\r\n'
    'endLocal & "%_prog%"  "%dp0%\\node_modules\\@anthropic-ai\\claude-code\\cli.js" %*\r\n'
)
EXE_SHIM = (
    '@ECHO off\r\n"%~dp0\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe"   %*\r\n'
)


def _package(folder: Path, shim: str, target: str) -> Path:
    claude = folder / "claude.cmd"
    claude.write_text(shim, encoding="utf-8")
    script = folder / "node_modules" / "@anthropic-ai" / "claude-code" / target
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    return claude


def test_a_script_shim_gives_node_and_the_script(tmp_path: Path) -> None:
    claude = _package(tmp_path, NODE_SHIM, "cli.js")
    (tmp_path / "node.exe").write_text("", encoding="utf-8")  # npm prefers the node beside it
    script = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js"
    assert resolve_shim(str(claude)) == [str(tmp_path / "node.exe"), str(script)]


def test_a_script_shim_takes_node_from_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude = _package(tmp_path, NODE_SHIM, "cli.js")
    monkeypatch.setattr("shutil.which", lambda name: "C:/node/node.exe" if name == "node" else None)
    assert resolve_shim(str(claude))[0] == "C:/node/node.exe"  # type: ignore[index]


def test_an_executable_shim_gives_the_executable(tmp_path: Path) -> None:
    claude = _package(tmp_path, EXE_SHIM, "bin/claude.exe")
    target = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    assert resolve_shim(str(claude)) == [str(target)]


def test_a_batch_file_that_is_not_understood_is_kept(tmp_path: Path) -> None:
    other = tmp_path / "claude.cmd"
    other.write_text("@ECHO off\r\nC:\\tools\\claude.exe %*\r\n", encoding="utf-8")
    assert resolve_shim(str(other)) is None
    assert find_claude(str(other)) == [str(other)]  # run as it is, as before


def test_a_shim_whose_target_is_missing_is_kept(tmp_path: Path) -> None:
    claude = tmp_path / "claude.cmd"
    claude.write_text(NODE_SHIM, encoding="utf-8")
    assert resolve_shim(str(claude)) is None


def test_an_executable_is_never_read_as_a_shim(tmp_path: Path) -> None:
    claude = tmp_path / "claude.exe"
    claude.write_text(NODE_SHIM, encoding="utf-8")
    assert not is_batch(str(claude))
    assert find_claude(str(claude)) == [str(claude)]


def test_find_claude_runs_the_program_of_a_chosen_shim(tmp_path: Path) -> None:
    claude = _package(tmp_path, EXE_SHIM, "bin/claude.exe")
    target = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    assert find_claude(str(claude)) == [str(target)]
