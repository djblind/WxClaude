# PyInstaller recipe: one folder (onedir), no console. Build with build.bat from the repo root.
from pathlib import Path

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
)

analysis = Analysis(
    [str(package / "__main__.py")],
    pathex=[str(root / "src")],
    datas=datas,
    # The Agent SDK is imported only when a message goes through it (core/claude/sdk_run.py).
    hiddenimports=["claude_agent_sdk", "wxclaude.core.claude.sdk_messages"],
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
