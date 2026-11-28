from collections.abc import Iterator
from pathlib import Path

import pytest

from wxclaude.core.config.model_loading import LOADING_METHODS, LmStudioLoading


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


@pytest.fixture(autouse=True)
def no_real_model_unloaded() -> Iterator[None]:
    """WxClaude unloads from LM Studio, when it ends, the models it prepared (``atexit``). A test
    must never leave one to unload: the models of the computer are the user's."""
    yield
    for method in LOADING_METHODS:
        if isinstance(method, LmStudioLoading):
            method._used.clear()
