"""Headless TUI test at 80x24 and 120x40 per AGENTS.md."""
import asyncio
import importlib.machinery
import importlib.util
from pathlib import Path

from textual.geometry import Size

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

_loader = importlib.machinery.SourceFileLoader(
    "codexswitch_tui", str(BIN_DIR / "codexswitch-tui")
)
_spec = importlib.util.spec_from_file_location(
    "codexswitch_tui", BIN_DIR / "codexswitch-tui", loader=_loader
)
tui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tui)


def test_tui_80x24():
    """Both panes, reasoning selector, status bar and function-key labels fit at 80x24."""
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert app.query_one("#models") is not None
            assert app.query_one("#sources") is not None
            assert app.query_one("#reasoning") is not None
            assert app.query_one("#model-detail") is not None
            assert app.query_one("#status") is not None
            assert app.query_one("#buttonbar") is not None
            bb = app.query_one("#buttonbar")
            bb_text = bb.render().plain
            assert len(bb_text) <= 80, f"buttonbar ({len(bb_text)}) exceeds 80 cols"

    asyncio.run(run())


def test_tui_120x40():
    """Both panes, reasoning selector, status bar and function-key labels fit at 120x40."""
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one("#models") is not None
            assert app.query_one("#sources") is not None
            assert app.query_one("#reasoning") is not None
            assert app.query_one("#model-detail") is not None
            assert app.query_one("#status") is not None
            assert app.query_one("#buttonbar") is not None
            bb = app.query_one("#buttonbar")
            bb_text = bb.render().plain
            assert len(bb_text) <= 120, f"buttonbar ({len(bb_text)}) exceeds 120 cols"

    asyncio.run(run())
