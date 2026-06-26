"""Headless TUI test at 80x24 and 120x40 per AGENTS.md."""
import asyncio
import importlib.machinery
import importlib.util
from pathlib import Path

from rich.text import Text
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


async def dismiss_splash(pilot) -> None:
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


def test_tui_subtitle_contains_version():
    assert tui.CodexSwitchApp.TITLE == "CodexSwitch Commander"
    assert "v0.5.9" in tui.CodexSwitchApp.SUB_TITLE
    assert "by WAM-Software since (c) 1988" in tui.CodexSwitchApp.SUB_TITLE


def test_startup_splash_contains_ascii_branding_and_credits():
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            dialog = app.screen.query_one("#splash-dialog")
            plain = dialog.render().plain
            assert "                    C O M M A N D E R" in plain
            assert "CodexSwitch Commander v0.5.9" in plain
            assert "by WAM-Software since (c) 1988" in plain
            assert "AI-assisted implementation: OpenAI Codex" in plain

    asyncio.run(run())


def test_codex_launch_argv_uses_resume_bypass_and_search():
    assert tui.codex_launch_argv("/usr/local/bin/codex") == [
        "/usr/local/bin/codex",
        "resume",
        "--dangerously-bypass-approvals-and-sandbox",
        "--search",
    ]


def test_button_bar_is_compact_commander_style():
    plain = Text.from_markup(tui.BUTTON_BAR).plain
    assert plain == (
        "1Help  2Prov  3Model 4Think 5Fresh 6Apply 7Auth  "
        "8Stat  9Codex 10Quit"
    )
    assert len(plain) <= 80


def test_tui_80x24():
    """Both panes, reasoning selector, status bar and function-key labels fit at 80x24."""
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            await dismiss_splash(pilot)
            assert app.query_one("#models") is not None
            assert app.query_one("#sources") is not None
            assert app.query_one("#reasoning") is not None
            assert app.query_one("#model-detail") is not None
            assert app.query_one("#status") is not None
            assert app.query_one("#buttonbar") is not None
            status = app.query_one("#status").render().plain
            assert "Ready · F1 Help · F6 Apply · F9 Codex" in status
            assert "WAM-Software" not in status
            bb = app.query_one("#buttonbar")
            bb_text = bb.render().plain
            assert len(bb_text) <= 80, f"buttonbar ({len(bb_text)}) exceeds 80 cols"

    asyncio.run(run())


def test_tui_120x40():
    """Both panes, reasoning selector, status bar and function-key labels fit at 120x40."""
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
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


def test_openai_auth_opens_device_sign_in_modal():
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            assert app.provider == "openai"
            await pilot.press("f7")
            await pilot.pause()
            dialog = app.screen.query_one("#openai-auth-dialog")
            assert "OPENAI DEVICE SIGN-IN" in dialog.render().plain
            assert "codex login --device-auth" in dialog.render().plain

    asyncio.run(run())


def test_provider_switch_keeps_models_and_accounts_exclusive():
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            for _ in range(3):
                await pilot.press("f2")
                await pilot.pause()
                source_ids = [
                    option.id for option in app.query_one("#sources").options
                ]

                app.query_one("#sources").highlighted = source_ids.index("provider:opencode-go")
                await pilot.pause()
                assert app.provider == "opencode-go"
                assert app.account is None
                opencode_ids = [
                    option.id for option in app.query_one("#models").options
                ]
                assert not any(
                    model_id.startswith("model:gpt-")
                    for model_id in opencode_ids
                )

                app.query_one("#sources").highlighted = source_ids.index("provider:openrouter")
                await pilot.pause()
                assert app.provider == "openrouter"
                assert app.account is None
                openrouter_ids = [
                    option.id for option in app.query_one("#models").options
                ]
                assert any(
                    model_id.startswith("model:openrouter/")
                    or "/" in model_id.removeprefix("model:")
                    for model_id in openrouter_ids
                )
                assert not any(
                    model_id.startswith("model:gpt-")
                    for model_id in openrouter_ids
                )

                app.query_one("#sources").highlighted = source_ids.index("provider:openai")
                await pilot.pause()
                assert app.provider == "openai"
                openai_ids = [
                    option.id for option in app.query_one("#models").options
                ]
                assert any(
                    model_id.startswith("model:gpt-")
                    for model_id in openai_ids
                )
                assert not any(
                    model_id == "model:kimi-k2.6"
                    for model_id in openai_ids
                )

    asyncio.run(run())
