from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def claude_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty Claude Code configuration folder: the tests never read the real one."""
    folder = tmp_path / "claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    return folder


@pytest.fixture(autouse=True)
def no_installed_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    """The copies of Claude Code of the Claude application on this computer are not found: a
    test sees only the PATH it sets."""
    monkeypatch.setattr("wxclaude.core.claude.runner.installed_claude", lambda: None)
