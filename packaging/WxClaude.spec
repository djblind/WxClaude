# PyInstaller recipe: one folder (onedir), no console. Build with build.bat from the repo root.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPECPATH).parent
package = root / "src" / "wxclaude"


def data(pattern: str, folder: str) -> list[tuple[str, str]]:
    """Files of the package kept at the same place, since the code reads them with resources."""
    return [(str(path), f"wxclaude/{folder}") for path in package.glob(pattern)]


datas = (
    data("locale/*/LC_MESSAGES/*.mo", "locale/fr/LC_MESSAGES")
    + data("data/*.txt", "data")
    + data("help/*.html", "help")
    + data("sounds/*.wav", "sounds")
    # The pseudo-console of the sign-in to another account (core/claude/account_token.py): its
    # helpers OpenConsole.exe and winpty-agent.exe sit next to the module.
    + collect_data_files("winpty", excludes=["tests/**"])
)

analysis = Analysis(
    [str(package / "__main__.py")],
    pathex=[str(root / "src")],
    datas=datas,
    binaries=collect_dynamic_libs("winpty"),
    # The Agent SDK is imported only when a message goes through it (core/claude/sdk_run.py), and
    # the pseudo-console only for a sign-in (core/claude/account_token.py).
    hiddenimports=["claude_agent_sdk", "wxclaude.core.claude.sdk_messages", "winpty"],
    excludes=["tkinter", "pytest", "mypy", "ruff"],
)
# The SDK carries its own claude program (about 400 MB); WxClaude gives it the user's one instead.
analysis.datas = [entry for entry in analysis.datas if "_bundled" not in entry[0]]
analysis.binaries = [entry for entry in analysis.binaries if "_bundled" not in entry[0]]
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="WxClaude",
    console=False,
)
coll = COLLECT(exe, analysis.binaries, analysis.datas, name="WxClaude")
