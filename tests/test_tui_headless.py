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

_backend = importlib.machinery.SourceFileLoader(
    "codexswitch", str(BIN_DIR / "codexswitch")
)
_backend_spec = importlib.util.spec_from_file_location(
    "codexswitch", BIN_DIR / "codexswitch", loader=_backend
)
cs = importlib.util.module_from_spec(_backend_spec)
_backend_spec.loader.exec_module(cs)


async def dismiss_splash(pilot) -> None:
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


def test_tui_subtitle_contains_version():
    assert tui.CodexSwitchApp.TITLE == "CodexSwitch Commander"
    assert f"v{cs.VERSION}" in tui.CodexSwitchApp.SUB_TITLE
    assert "by WAM-Software since (c) 1988" in tui.CodexSwitchApp.SUB_TITLE


def test_startup_splash_contains_ascii_branding_and_credits():
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            dialog = app.screen.query_one("#splash-dialog")
            plain = dialog.render().plain
            assert "                    C O M M A N D E R" in plain
            assert f"CodexSwitch Commander v{cs.VERSION}" in plain
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


def test_main_checks_codex_runtime_before_exec(monkeypatch):
    calls = []

    class FakeApp:
        launch_codex = True

        def run(self):
            calls.append("run")

    monkeypatch.setattr(tui, "CodexSwitchApp", FakeApp)
    monkeypatch.setitem(
        tui.BACKEND,
        "ensure_codex_runtime_writable",
        lambda: calls.append("preflight"),
    )
    monkeypatch.setattr(tui, "codex_launch_argv", lambda: ["/bin/echo", "codex"])

    def fake_execvp(binary, argv):
        calls.append(("exec", binary, argv))
        raise SystemExit(0)

    monkeypatch.setattr(tui.os, "execvp", fake_execvp)

    import pytest

    with pytest.raises(SystemExit):
        tui.main()

    assert calls == ["run", "preflight", ("exec", "/bin/echo", ["/bin/echo", "codex"])]


def test_button_bar_is_segmented_commander_style():
    assert tui.FUNCTION_KEYS == (
        ("1", "Help"),
        ("2", "Prov"),
        ("3", "Model"),
        ("4", "Think"),
        ("5", "Fresh"),
        ("6", "Apply"),
        ("7", "Auth"),
        ("8", "Stat"),
        ("9", "Codex"),
        ("10", "Quit"),
    )


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
            assert status.strip() == "Ready"
            assert "F1 Help" not in status
            assert "F6 Apply" not in status
            assert "WAM-Software" not in status
            bb = app.query_one("#buttonbar")
            keys = list(bb.query(".fkey"))
            assert len(keys) == 10
            assert [key.render().plain.strip() for key in keys] == [
                "1 Help",
                "2 Prov",
                "3 Model",
                "4 Think",
                "5 Fresh",
                "6 Apply",
                "7 Auth",
                "8 Stat",
                "9 Codex",
                "10 Quit",
            ]

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
            assert len(list(bb.query(".fkey"))) == 10

    asyncio.run(run())


def test_tui_panes_share_commander_grid_at_common_sizes():
    """Top and lower right panes should line up like a Commander split view."""

    async def check(size):
        app = tui.CodexSwitchApp()
        async with app.run_test(size=size) as pilot:
            await dismiss_splash(pilot)
            source = app.query_one("#source-pane").region
            reason = app.query_one("#reason-box").region
            model = app.query_one("#model-pane").region
            detail = app.query_one("#detail-box").region
            workspace = app.query_one("#workspace").region
            lower = app.query_one("#lower-pane").region
            status = app.query_one("#status").region
            buttonbar = app.query_one("#buttonbar").region

            assert source.x == reason.x
            assert source.width == reason.width == 38
            assert model.x == detail.x == workspace.x == lower.x == status.x
            assert model.width == detail.width
            assert status.width == workspace.width == lower.width
            assert buttonbar.x == 0
            assert buttonbar.width == size[0]

    asyncio.run(check((80, 24)))
    asyncio.run(check((120, 40)))


def test_reasoning_enter_starts_codex_and_status_previews_selection(monkeypatch):
    app = tui.CodexSwitchApp()
    started = {"codex": False}

    def fake_action_codex():
        started["codex"] = True

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            monkeypatch.setattr(app, "action_codex", fake_action_codex)
            await pilot.press("enter")
            await pilot.pause()
            assert app.query_one("#reasoning").has_focus
            assert "Enter starts Codex" in app.query_one("#status").render().plain
            await pilot.press("enter")
            await pilot.pause()
            assert started["codex"] is True

    asyncio.run(run())


def test_openai_status_preview_shows_active_codex_account(monkeypatch):
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            app.provider = "openai"
            app.account = "active@example.test"
            app.model = "gpt-test"
            app.show_ready_to_start("medium")
            status = app.query_one("#status").render().plain
            assert "Ready: openai / gpt-test / medium" in status
            assert "acct: active@example.test" in status

    asyncio.run(run())


def test_openai_auth_opens_device_sign_in_modal():
    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            source_ids = [option.id for option in app.query_one("#sources").options]
            app.query_one("#sources").highlighted = source_ids.index("provider:openai")
            await pilot.pause()
            assert app.provider == "openai"
            await pilot.press("f7")
            await pilot.pause()
            dialog = app.screen.query_one("#openai-auth-dialog")
            assert "OPENAI DEVICE SIGN-IN" in dialog.render().plain
            assert "codex login --device-auth" in dialog.render().plain
            assert "https://chatgpt.com/activate" in dialog.render().plain
            assert not app.screen.query("#start-openai-auth")

    asyncio.run(run())


def test_provider_api_key_popup_saves_openrouter_key(monkeypatch):
    saved = {}
    monkeypatch.setitem(
        tui.BACKEND,
        "save_openrouter_key",
        lambda key: saved.update({"openrouter": key}),
    )
    monkeypatch.setitem(tui.BACKEND, "refresh_openrouter_models", lambda strict=False: True)

    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            app.provider = "openrouter"
            app.action_auth()
            await pilot.pause()
            assert app.screen.query_one("#api-key-input")
            await pilot.click("#api-key-input")
            await pilot.press("o", "r", "-", "t", "e", "s", "t")
            await pilot.press("enter")
            await pilot.pause()
            assert saved == {"openrouter": "or-test"}

    asyncio.run(run())


def test_provider_api_key_popup_saves_opencode_go_key(monkeypatch):
    saved = {}
    monkeypatch.setitem(
        tui.BACKEND,
        "save_opencode_go_key",
        lambda key: saved.update({"opencode": key}),
    )
    monkeypatch.setitem(tui.BACKEND, "refresh_opencode_models", lambda strict=False: True)

    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            app.provider = "opencode-go"
            app.action_auth()
            await pilot.pause()
            assert app.screen.query_one("#api-key-input")
            await pilot.click("#api-key-input")
            await pilot.press("o", "c", "-", "t", "e", "s", "t")
            await pilot.press("enter")
            await pilot.pause()
            assert saved == {"opencode": "oc-test"}

    asyncio.run(run())


def test_opencode_details_show_token_limits_and_reasoning(monkeypatch):
    monkeypatch.setitem(tui.BACKEND, "opencode_go_key_present", lambda: True)
    monkeypatch.setitem(
        tui.BACKEND,
        "reasoning_choices",
        lambda model: [("low", "low"), ("high", "high")],
    )
    monkeypatch.setitem(tui.BACKEND, "read_json", lambda path, default: {})

    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            app.provider = "opencode-go"
            app.model = "model-x"
            app.catalog = {
                "model-x": {
                    "name": "Model X",
                    "family": "Test",
                    "limit": {"context": 123456, "output": 7890},
                    "capabilities": {"input": {"text": True}, "toolcall": True},
                    "status": "active",
                }
            }
            app.update_details()
            detail = app.query_one("#model-detail").render().plain
            assert "Tokens: 123,456 context / 7,890 output" in detail
            reason_ids = [option.id for option in app.query_one("#reasoning").options]
            assert reason_ids == ["reason:low", "reason:high"]

    asyncio.run(run())


def test_openrouter_mandatory_without_efforts_is_model_managed(monkeypatch):
    state = {"provider": "openrouter", "model": "aion-labs/aion-2.0"}

    def fake_read_json(path, default):
        if path == tui.BACKEND["SWITCH_CONFIG"]:
            return state
        return default

    monkeypatch.setitem(tui.BACKEND, "read_json", fake_read_json)
    monkeypatch.setitem(tui.BACKEND, "openrouter_key_present", lambda: True)
    monkeypatch.setitem(tui.BACKEND, "openrouter_reasoning_choices", lambda model: [])
    monkeypatch.setitem(
        tui.BACKEND,
        "openrouter_model_catalog",
        lambda refresh=False: {
            "aion-labs/aion-2.0": {
                "name": "Aion 2.0",
                "context_length": 131072,
                "reasoning": {"mandatory": True},
                "architecture": {"input_modalities": ["text"]},
            }
        },
    )

    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            app.provider = "openrouter"
            app.model = "aion-labs/aion-2.0"
            app.update_details()
            detail = app.query_one("#model-detail").render().plain
            assert "Tokens: 131,072 context / ? output" in detail
            reasoning = app.query_one("#reasoning")
            assert [option.id for option in reasoning.options] == [
                f"reason:{tui.DEFAULT_REASONING_VALUE}"
            ]
            assert "model-managed" in str(reasoning.options[0].prompt)
            assert app.selected_reasoning() is None

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


def test_openrouter_apply_status_uses_persisted_reasoning_state(monkeypatch):
    """OpenRouter status must not show transient medium when config did not store it."""
    state = {"provider": "openrouter", "model": "openrouter/auto"}

    def fake_read_json(path, default):
        if path == tui.BACKEND["SWITCH_CONFIG"]:
            return state
        return default

    monkeypatch.setitem(tui.BACKEND, "read_json", fake_read_json)
    monkeypatch.setitem(tui.BACKEND, "openrouter_models", lambda: ["openrouter/auto"])
    monkeypatch.setitem(tui.BACKEND, "openrouter_model_catalog", lambda refresh=False: {})
    monkeypatch.setitem(tui.BACKEND, "openrouter_reasoning_choices", lambda model: [])
    monkeypatch.setitem(tui.BACKEND, "default_reasoning_effort", lambda model: "medium")
    monkeypatch.setitem(tui.BACKEND, "validate_provider_model", lambda provider, model: None)
    monkeypatch.setitem(
        tui.BACKEND,
        "update_codex_config",
        lambda provider, model, effort=None: state.update(
            {"provider": provider, "model": model}
        ),
    )
    monkeypatch.setitem(tui.BACKEND, "openrouter_key_present", lambda: True)

    app = tui.CodexSwitchApp()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await dismiss_splash(pilot)
            assert app.provider == "openrouter"
            assert app.model == "openrouter/auto"
            app.action_apply()
            await pilot.pause()
            assert app.query_one("#status").render().plain.strip() == (
                "Active: openrouter / openrouter/auto"
            )

    asyncio.run(run())
