"""Deterministic headless coverage for the Commander TUI.

The real backend is deliberately never used after module import.  Every app in
this file receives a mapping-compatible fake backend and an isolated TUI state
path so the tests cannot inspect the developer's HOME, credentials, caches, or
network.
"""

from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
import json
import threading
from pathlib import Path
from typing import Any, Callable

import pytest
from rich.text import Text
from textual.color import Color
from textual.geometry import Size
from textual.widgets import Button, Input, OptionList


BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

_loader = importlib.machinery.SourceFileLoader(
    "codexswitch_tui", str(BIN_DIR / "codexswitch-tui")
)
_spec = importlib.util.spec_from_file_location(
    "codexswitch_tui", BIN_DIR / "codexswitch-tui", loader=_loader
)
tui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tui)

_backend_loader = importlib.machinery.SourceFileLoader(
    "codexswitch", str(BIN_DIR / "codexswitch")
)
_backend_spec = importlib.util.spec_from_file_location(
    "codexswitch", BIN_DIR / "codexswitch", loader=_backend_loader
)
cs = importlib.util.module_from_spec(_backend_spec)
_backend_spec.loader.exec_module(cs)


class FakeBackend(dict[str, Any]):
    """Small stateful implementation of the backend mapping used by the TUI."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.switch_config = root / "config" / "codexswitch.json"
        self.codex_home = root / "codex"
        self.calls: list[tuple[Any, ...]] = []
        self.config_state: dict[str, Any] = {
            "provider": "openai",
            "model": "gpt-main",
            "reasoning_effort": "medium",
        }
        self.codex_state: dict[str, Any] = {
            "model_provider": "openai",
            "model": "gpt-main",
            "model_reasoning_effort": "medium",
        }
        self.auth_state: dict[str, Any] = {"email": "tester@example.invalid"}
        self.azure_state: dict[str, Any] = {
            "endpoint": "https://example.invalid/openai/v1",
        }
        self.openai_catalog: dict[str, dict[str, Any]] = {
            "gpt-main": {
                "display_name": "GPT Main",
                "context_window": 200_000,
                "max_output_tokens": 32_000,
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": [
                    {"effort": "low"},
                    {"effort": "medium"},
                    {"effort": "high"},
                ],
            },
            "gpt-alpha": {
                "display_name": "Alpha [Preview] Ω",
                "context_window": 128_000,
                "max_output_tokens": 16_000,
                "default_reasoning_level": "low",
                "supported_reasoning_levels": [
                    {"effort": "low"},
                    {"effort": "medium"},
                    {"effort": "high"},
                ],
            },
            "gpt-beta": {
                "display_name": "Beta",
                "context_window": 64_000,
                "max_output_tokens": 8_000,
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": [
                    {"effort": "low"},
                    {"effort": "medium"},
                    {"effort": "high"},
                ],
            },
        }
        self.opencode_catalog: dict[str, dict[str, Any]] = {
            "oc-fast": {
                "name": "OC Fast",
                "family": "OpenCode",
                "limit": {"context": 131_072, "output": 16_384},
                "capabilities": {
                    "input": {"text": True},
                    "toolcall": True,
                },
                "status": "active",
            },
            "oc-think": {
                "name": "OC Think",
                "family": "OpenCode",
                "limit": {"context": 262_144, "output": 32_768},
                "capabilities": {
                    "input": {"text": True},
                    "toolcall": True,
                },
                "status": "active",
            },
        }
        self.openrouter_catalog: dict[str, dict[str, Any]] = {
            "openrouter/auto": {
                "name": "OpenRouter Auto",
                "context_length": 200_000,
                "architecture": {"input_modalities": ["text"]},
                "reasoning": {},
            },
            "vendor/think": {
                "name": "Vendor Think",
                "context_length": 100_000,
                "max_completion_tokens": 12_000,
                "architecture": {"input_modalities": ["text"]},
                "reasoning": {"mandatory": True},
            },
        }

        self.update(
            {
                "VERSION": cs.VERSION,
                "BRAND_BANNER": cs.BRAND_BANNER,
                "ASCII_LOGO_WIDTH": cs.ASCII_LOGO_WIDTH,
                "CREDITS_OWNER": cs.CREDITS_OWNER,
                "CREDITS_AI": cs.CREDITS_AI,
                "HOME": root,
                "CODEX_HOME": self.codex_home,
                "SWITCH_CONFIG": self.switch_config,
                "DEFAULT_OPENCODE_MODEL": "oc-fast",
                "OPENAI_FALLBACK_MODELS": list(self.openai_catalog),
                "OPENAI_FALLBACK_CATALOG": dict(self.openai_catalog),
                "AZURE_MODELS": ["azure-gpt"],
                "AZURE_REASONING_CHOICES": [
                    ("Low (default)", "low"),
                    ("Medium", "medium"),
                    ("High", "high"),
                    ("Extra high", "xhigh"),
                    ("Max", "max"),
                    ("Ultra", "ultra"),
                ],
                "AZURE_DEFAULT_REASONING_EFFORT": "low",
                "OPENCODE_GO_FALLBACK_CATALOG": dict(self.opencode_catalog),
                "OPENROUTER_FALLBACK_MODELS": ["openrouter/auto"],
                "AZURE_DEFAULT_ENDPOINT": "https://example.invalid/azure",
                "AZURE_DEFAULT_API_VERSION": "2026-01-01",
                "read_json": self.read_json,
                "openai_auth_email": self.openai_auth_email,
                "openai_accounts": lambda: ["tester@example.invalid"],
                "openai_models": lambda: list(self.openai_catalog),
                "azure_models": lambda: ["azure-gpt"],
                "opencode_models": lambda: list(self.opencode_catalog),
                "openrouter_models": lambda: list(self.openrouter_catalog),
                "openai_model_catalog": lambda refresh=False: dict(
                    self.openai_catalog
                ),
                "opencode_model_catalog": lambda refresh=False: dict(
                    self.opencode_catalog
                ),
                "openrouter_model_catalog": lambda refresh=False: dict(
                    self.openrouter_catalog
                ),
                "openai_reasoning_choices": self.reasoning_choices,
                "reasoning_choices": self.reasoning_choices,
                "openrouter_reasoning_choices": self.router_reasoning_choices,
                "default_reasoning_effort": lambda model: "medium",
                "opencode_go_key_present": lambda: True,
                "openrouter_key_present": lambda: True,
                "azure_credentials": lambda: dict(self.azure_state),
                "azure_credentials_present": lambda: True,
                "codex_config_state": lambda: dict(self.codex_state),
                "validate_provider_model": self.validate_provider_model,
                "update_codex_config": self.update_codex_config,
                "use_openai_account": self.use_openai_account,
                "save_openrouter_key": lambda key: self.calls.append(
                    ("save-key", "openrouter")
                ),
                "save_opencode_go_key": lambda key: self.calls.append(
                    ("save-key", "opencode-go")
                ),
                "save_azure_credentials": self.save_azure_credentials,
                "refresh_openai_models": self.refresher("openai"),
                "refresh_opencode_models": self.refresher("opencode-go"),
                "refresh_openrouter_models": self.refresher("openrouter"),
                "ensure_codex_runtime_writable": lambda: self.calls.append(
                    ("preflight",)
                ),
                "codex_bin": lambda: "/usr/bin/codex-test",
                "codex_launch_environment": lambda: {"TEST_CODEX_ENV": "1"},
                "enable_vault_session_cache": lambda home: self.calls.append(
                    ("vault-cache-enable", Path(home))
                ),
                "refresh_vault_session_cache": lambda home: self.calls.append(
                    ("vault-cache-refresh", Path(home))
                )
                or {},
                "vault_status": lambda: {
                    "mode": "local",
                    "online": True,
                    "label": "LOCAL",
                },
            }
        )

    def read_json(self, path: Path, default: Any) -> Any:
        path = Path(path)
        if path == self.switch_config:
            return dict(self.config_state)
        if path == self.codex_home / "auth.json":
            return dict(self.auth_state)
        return default

    @staticmethod
    def openai_auth_email(auth: dict[str, Any]) -> str | None:
        return auth.get("email")

    @staticmethod
    def reasoning_choices(model: str) -> list[tuple[str, str]]:
        return [("low", "low"), ("medium", "medium"), ("high", "high")]

    def router_reasoning_choices(self, model: str) -> list[tuple[str, str]]:
        if self.openrouter_catalog.get(model, {}).get("reasoning", {}).get(
            "mandatory"
        ):
            return []
        return [("low", "low"), ("high", "high")]

    def validate_provider_model(self, provider: str, model: str) -> None:
        self.calls.append(("validate", provider, model))

    def update_codex_config(
        self, provider: str, model: str, effort: str | None = None
    ) -> None:
        self.calls.append(("apply", provider, model, effort))
        self.config_state = {"provider": provider, "model": model}
        self.codex_state = {"model_provider": provider, "model": model}
        if effort:
            self.config_state["reasoning_effort"] = effort
            self.codex_state["model_reasoning_effort"] = effort
        if provider == "openai" and self.auth_state.get("email"):
            self.config_state["openai_account"] = self.auth_state["email"]
        elif provider != "openai":
            self.config_state.pop("openai_account", None)

    def use_openai_account(self, email: str) -> None:
        self.calls.append(("use-account", email))
        self.auth_state = {"email": email}
        self.config_state["openai_account"] = email

    def save_azure_credentials(self, endpoint: str, key: str) -> None:
        self.calls.append(("save-key", "azure"))
        self.azure_state = {"endpoint": endpoint}

    def refresher(self, provider: str) -> Callable[[bool], bool]:
        def refresh(strict: bool = False) -> bool:
            self.calls.append(("refresh", provider, strict))
            return True

        return refresh


@pytest.fixture
def fake_backend(tmp_path: Path) -> FakeBackend:
    return FakeBackend(tmp_path)


@pytest.fixture
def app_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    created = 0

    def unexpected_subprocess(*args: Any, **kwargs: Any) -> None:
        pytest.fail("the headless TUI test tried to start a subprocess")

    monkeypatch.setattr(tui.subprocess, "run", unexpected_subprocess)
    monkeypatch.setattr(tui.os, "execvp", unexpected_subprocess)

    def factory(
        backend: FakeBackend | None = None,
        *,
        state_path: Path | None = None,
        splash_seen: bool = True,
        refresh_on_start: bool = False,
    ):
        nonlocal created
        created += 1
        backend = backend or FakeBackend(tmp_path / f"backend-{created}")
        state_path = state_path or tmp_path / f"tui-state-{created}.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        if splash_seen:
            state_path.write_text(
                json.dumps({"splash_version": cs.VERSION}), encoding="utf-8"
            )
        elif state_path.exists():
            state_path.unlink()
        # Screen classes also used the module mapping historically.  Patching it
        # makes an accidental fallback deterministic while constructor injection
        # remains the API under test.
        monkeypatch.setattr(tui, "BACKEND", backend)
        return tui.CodexSwitchApp(
            backend=backend,
            state_path=state_path,
            refresh_on_start=refresh_on_start,
        )

    return factory


async def settle(pilot, turns: int = 2) -> None:
    for _ in range(turns):
        await pilot.pause()


async def wait_until(
    pilot, predicate: Callable[[], bool], *, attempts: int = 80
) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause(0.01)
    assert predicate()


def option_plain(option: Any) -> str:
    prompt = option.prompt
    return prompt.plain if isinstance(prompt, Text) else str(prompt)


def option_by_id(option_list: OptionList, option_id: str):
    return next(option for option in option_list.options if option.id == option_id)


def highlight(option_list: OptionList, option_id: str) -> None:
    option_list.highlighted = next(
        index
        for index, option in enumerate(option_list.options)
        if option.id == option_id
    )


def literal_style(text: Text, literal: str) -> Any:
    span = next(
        span for span in text.spans if text.plain[span.start : span.end] == literal
    )
    return span.style


def test_tui_header_is_compact_and_credits_move_out_of_it():
    assert tui.CodexSwitchApp.TITLE == "CodexSwitch Commander"
    assert f"v{cs.VERSION}" in tui.CodexSwitchApp.SUB_TITLE
    assert "WAM-Software" not in tui.CodexSwitchApp.SUB_TITLE
    assert "AI-assisted" not in tui.CodexSwitchApp.SUB_TITLE


def test_splash_is_once_per_version_and_fits_80x24(
    app_factory, fake_backend: FakeBackend, tmp_path: Path
):
    state_path = tmp_path / "shared-tui-state.json"
    app = app_factory(
        fake_backend, state_path=state_path, splash_seen=False
    )

    async def first_run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            dialog = app.screen.query_one("#splash-dialog")
            plain = dialog.render().plain
            assert f"CodexSwitch Commander v{cs.VERSION}" in plain
            assert cs.CREDITS_OWNER in plain
            assert cs.CREDITS_AI in plain
            assert dialog.region.x >= 0 and dialog.region.y >= 0
            assert dialog.region.right <= 80 and dialog.region.bottom <= 24
            await pilot.press("enter")
            await settle(pilot)

    asyncio.run(first_run())
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "splash_version": cs.VERSION
    }

    second_app = app_factory(
        fake_backend, state_path=state_path, splash_seen=True
    )

    async def second_run() -> None:
        async with second_app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            assert not second_app.screen.query("#splash-dialog")
            assert second_app.query_one("#sources").has_focus

    asyncio.run(second_run())


@pytest.mark.parametrize(
    ("size", "expected_widths"),
    [
        ((80, 24), (24, 34, 20)),
        ((120, 40), (32, 58, 28)),
    ],
)
def test_three_pane_layout_has_exact_commander_geometry(
    app_factory, size: tuple[int, int], expected_widths: tuple[int, int, int]
):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=size) as pilot:
            await settle(pilot)
            sources = app.query_one("#source-pane").region
            models = app.query_one("#model-pane").region
            reasoning = app.query_one("#reason-box").region
            detail = app.query_one("#detail-box").region
            workspace = app.query_one("#workspace").region
            status = app.query_one("#status").region
            buttonbar = app.query_one("#buttonbar").region

            assert (sources.width, models.width, reasoning.width) == expected_widths
            assert sources.x == workspace.x == detail.x == status.x == 1
            assert models.x == sources.right
            assert reasoning.x == models.right
            assert reasoning.right == workspace.right == size[0] - 1
            assert sources.y == models.y == reasoning.y
            assert sources.height == models.height == reasoning.height
            assert detail.y == workspace.bottom
            assert detail.width == status.width == size[0] - 2
            assert detail.height == 7
            assert status.y == detail.bottom
            assert buttonbar.x == 0 and buttonbar.width == size[0]
            assert buttonbar.bottom == size[1]

    asyncio.run(run())


def test_status_omits_account_only_in_compact_layout(app_factory):
    async def rendered_status(size: tuple[int, int]) -> str:
        app = app_factory()
        async with app.run_test(size=size) as pilot:
            await settle(pilot)
            return app.query_one("#status").render().plain

    compact = asyncio.run(rendered_status((80, 24)))
    wide = asyncio.run(rendered_status((120, 40)))
    assert "acct:" not in compact
    assert "acct: tester@example.invalid" in wide


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (
            (80, 24),
            [
                "F1 Help",
                "F2 Prov",
                "F3 Model",
                "F4 Think",
                "F5 Refr",
                "F6 Apply",
                "F7 Auth",
                "F8 Stat",
                "F9 Start",
                "F10 Quit",
            ],
        ),
        (
            (100, 24),
            [
                "F1 Help",
                "F2 Prov",
                "F3 Model",
                "F4 Think",
                "F5 Refr",
                "F6 Apply",
                "F7 Auth",
                "F8 Stat",
                "F9 Start",
                "F10 Quit",
            ],
        ),
        (
            (120, 40),
            [
                "F1 Help",
                "F2 Providers",
                "F3 Models",
                "F4 Reasoning",
                "F5 Refresh",
                "F6 Apply",
                "F7 Auth",
                "F8 Status",
                "F9 Start",
                "F10 Quit",
            ],
        ),
    ],
)
def test_function_bar_uses_compact_and_wide_labels(app_factory, size, expected):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=size) as pilot:
            await settle(pilot)
            assert [key.render().plain for key in app.query(".fkey")] == expected

    asyncio.run(run())


def test_resize_warning_preserves_pending_selection_and_focus(app_factory):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            await pilot.press("right", "down")
            await settle(pilot)
            assert app.model == "gpt-alpha"
            assert app.query_one("#models").has_focus

            await pilot.resize_terminal(79, 23)
            await settle(pilot)
            warning = app.query_one("#size-warning")
            assert warning.styles.display == "block"
            assert "Minimum terminal size: 80×24" in warning.render().plain
            await pilot.press("down", "right", "end")
            await settle(pilot)
            assert app.model == "gpt-alpha"

            await pilot.resize_terminal(80, 24)
            await settle(pilot)
            assert warning.styles.display == "none"
            assert app.model == "gpt-alpha"
            assert app.query_one("#models").has_focus

    asyncio.run(run())


def test_arrow_and_tab_navigation_follow_provider_model_reasoning_order(app_factory):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources")
            models = app.query_one("#models")
            reasoning = app.query_one("#reasoning")

            assert sources.has_focus
            await pilot.press("left")
            assert sources.has_focus  # no wrap at the first panel
            await pilot.press("right")
            assert models.has_focus
            await pilot.press("right")
            assert reasoning.has_focus
            await pilot.press("right")
            assert reasoning.has_focus  # no wrap at the last panel
            await pilot.press("left", "left")
            assert sources.has_focus

            await pilot.press("tab")
            assert models.has_focus
            assert "ENTER: REASONING" in app.query_one("#status").render().plain.upper()
            await pilot.press("tab")
            assert reasoning.has_focus
            assert "ENTER: START" in app.query_one("#status").render().plain.upper()
            await pilot.press("tab")
            assert sources.has_focus  # Tab deliberately cycles
            await pilot.press("shift+tab")
            assert reasoning.has_focus

    asyncio.run(run())


def test_plain_key_aliases_focus_panels_and_open_help(app_factory):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            assert app.query_one("#models").has_focus
            await pilot.press("t")
            assert app.query_one("#reasoning").has_focus
            await pilot.press("p")
            assert app.query_one("#sources").has_focus
            await pilot.press("?")
            await settle(pilot)
            assert app.screen.query("#help-dialog")
            await pilot.press("escape")
            assert app.query_one("#sources").has_focus

    asyncio.run(run())


def test_enter_advances_panels_and_final_enter_applies_then_launches(
    app_factory, fake_backend: FakeBackend, monkeypatch: pytest.MonkeyPatch
):
    app = app_factory(fake_backend)
    exit_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exit_calls.append(args))

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert app.query_one("#sources").has_focus
            await pilot.press("enter")
            assert app.query_one("#models").has_focus
            await pilot.press("down")
            await settle(pilot)
            assert app.model == "gpt-alpha"
            await pilot.press("enter")
            assert app.query_one("#reasoning").has_focus
            await pilot.press("enter")
            await wait_until(pilot, lambda: app.launch_codex)

            assert any(
                call[:3] == ("apply", "openai", "gpt-alpha")
                for call in fake_backend.calls
            )
            assert app.launch_codex is True
            assert exit_calls

    asyncio.run(run())


def test_active_and_pending_markers_remain_distinct(app_factory):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            assert "●" in option_plain(option_by_id(models, "model:gpt-main"))

            await pilot.press("right", "down")
            await settle(pilot)

            assert app.model == "gpt-alpha"
            assert "●" in option_plain(option_by_id(models, "model:gpt-main"))
            assert "◆" in option_plain(option_by_id(models, "model:gpt-alpha"))
            assert app.selection_is_dirty() is True
            assert "PENDING" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_dirty_quit_requires_confirmation_and_can_be_cancelled(
    app_factory, monkeypatch: pytest.MonkeyPatch
):
    app = app_factory()
    exit_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exit_calls.append(args))

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            await pilot.press("right", "down")
            await settle(pilot)
            assert app.selection_is_dirty()

            await pilot.press("q")
            await settle(pilot)
            assert app.screen.query("#quit-dialog")
            await pilot.press("escape")
            await settle(pilot)
            assert not exit_calls
            assert app.query_one("#models").has_focus
            assert app.selection_is_dirty()

            await pilot.press("f10", "enter")
            await settle(pilot)
            assert exit_calls

    asyncio.run(run())


def test_escape_and_f8_restore_active_selection_and_clear_search(
    app_factory
):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:openrouter")
            await settle(pilot)
            assert app.provider == "openrouter"
            await pilot.press("escape")
            await settle(pilot)
            assert app.provider == "openai"
            assert app.model == "gpt-main"

            await pilot.press("f3", "/", *"gpt-beta")
            await settle(pilot)
            assert app.model == "gpt-beta"
            await pilot.press("f8")
            await settle(pilot)
            assert app.provider == "openai"
            assert app.model == "gpt-main"
            assert app.model_filter_query == ""
            assert app.query_one("#model-filter").styles.display == "none"
            assert not app.selection_is_dirty()

    asyncio.run(run())


def test_model_search_matches_full_id_and_display_name(app_factory):
    app = app_factory(refresh_on_start=True)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await app.workers.wait_for_complete()
            await settle(pilot)
            await pilot.press("f3", "/")
            await settle(pilot)
            model_filter = app.query_one("#model-filter", Input)
            assert model_filter.has_focus
            await pilot.press("p", "r", "e", "v", "i", "e", "w")
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            assert [option.id for option in models.options] == ["model:gpt-alpha"]
            await pilot.press("enter")
            await settle(pilot)
            assert app.model == "gpt-alpha"
            assert app.query_one("#reasoning").has_focus

            await pilot.press("f3", "/", "g", "p", "t", "-", "b", "e", "t", "a")
            await settle(pilot)
            assert [option.id for option in models.options] == ["model:gpt-beta"]
            await pilot.press("escape")
            await settle(pilot)
            assert {option.id for option in models.options} == {
                "model:gpt-main",
                "model:gpt-alpha",
                "model:gpt-beta",
            }
            assert app.model == "gpt-beta"

    asyncio.run(run())


def test_startup_loads_cached_catalogs_without_refreshing_providers(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend, refresh_on_start=True)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await app.workers.wait_for_complete()
            await settle(pilot)
            assert not [call for call in fake_backend.calls if call[0] == "refresh"]
            assert [
                call for call in fake_backend.calls if call[0] == "vault-cache-enable"
            ]

    asyncio.run(run())


def test_f5_explicitly_refreshes_vault_session_cache(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await pilot.press("f5")
            await wait_until(
                pilot,
                lambda: any(
                    call[0] == "vault-cache-refresh"
                    for call in fake_backend.calls
                ),
            )
            await app.workers.wait_for_complete()

    asyncio.run(run())


def test_remote_vault_offline_is_persistent_and_visible_in_status_bar(
    app_factory, fake_backend: FakeBackend
):
    fake_backend["vault_status"] = lambda: {
        "mode": "remote",
        "online": False,
        "label": "OFFLINE",
    }
    app = app_factory(fake_backend, refresh_on_start=True)

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await wait_until(
                pilot,
                lambda: "UNAVAILABLE"
                in app.query_one("#status").render().plain.upper(),
            )
            status = app.query_one("#status").render().plain.upper()
            assert "VAULT OFFLINE" in status
            assert "ERROR" in status
            badge = literal_style(app.query_one("#status").render(), "VAULT OFFLINE")
            assert badge.foreground == Color.parse("#ffffff")
            assert badge.background == Color.parse("#af0000")

    asyncio.run(run())


def test_remote_vault_online_badge_is_white_on_green(
    app_factory, fake_backend: FakeBackend
):
    fake_backend["vault_status"] = lambda: {
        "mode": "remote",
        "online": True,
        "label": "ONLINE",
    }
    app = app_factory(fake_backend, refresh_on_start=True)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await wait_until(
                pilot,
                lambda: "VAULT ONLINE"
                in app.query_one("#status").render().plain.upper(),
            )
            badge = literal_style(app.query_one("#status").render(), "VAULT ONLINE")
            assert badge.foreground == Color.parse("#ffffff")
            assert badge.background == Color.parse("#008700")

    asyncio.run(run())


def test_model_search_no_results_blocks_apply_and_start(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            await pilot.press("f3", "/")
            await pilot.press(*"does-not-exist")
            await settle(pilot)
            assert not [
                option
                for option in app.query_one("#models", OptionList).options
                if option.id and option.id.startswith("model:")
            ]
            await pilot.press("enter", "f9")
            await settle(pilot)
            assert not any(call[0] == "apply" for call in fake_backend.calls)
            assert app.launch_codex is False
            assert "NO" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_auth_cancel_preserves_pending_selection_and_restores_focus(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:openrouter")
            await settle(pilot)
            before = (app.provider, app.account, app.model)
            await pilot.press("f7")
            await settle(pilot)
            assert app.screen.query_one("#api-key-input")
            await pilot.press("escape")
            await settle(pilot)
            assert (app.provider, app.account, app.model) == before
            assert sources.has_focus
            assert not any(call[0] == "save-key" for call in fake_backend.calls)

    asyncio.run(run())


def test_openai_device_auth_result_survives_focus_restoration(
    app_factory,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
):
    app = app_factory(fake_backend)
    monkeypatch.setattr(tui.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "suspend", lambda: tui.contextlib.nullcontext())

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            app.remember_modal_focus()
            app.run_openai_device_auth()
            await settle(pilot)

            status = app.query_one("#status").render().plain
            assert "OpenAI account added" in status
            assert fake_backend.auth_state["email"] in status
            assert app.query_one("#sources").has_focus

    asyncio.run(run())


def test_auth_save_targets_the_pending_provider_only(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:openrouter")
            await settle(pilot)
            await pilot.press("f7")
            await settle(pilot)
            assert app.screen.query_one("#api-key-input", Input).has_focus
            await pilot.press("t", "e", "s", "t", "enter")
            await wait_until(
                pilot,
                lambda: ("save-key", "openrouter") in fake_backend.calls,
            )
            assert ("save-key", "opencode-go") not in fake_backend.calls
            refreshes = [call for call in fake_backend.calls if call[0] == "refresh"]
            assert refreshes == [("refresh", "openrouter", False)]

    asyncio.run(run())


def test_credential_refresh_failure_retains_existing_catalog(
    app_factory, fake_backend: FakeBackend
):
    fake_backend["OPENROUTER_FALLBACK_MODELS"] = [
        "openrouter/auto",
        "vendor/think",
    ]
    fake_backend["refresh_openrouter_models"] = lambda strict=False: False
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:openrouter")
            await settle(pilot)
            before = list(app.model_lists["openrouter"])

            await pilot.press("f7")
            await settle(pilot)
            await pilot.press(*"test-key", "enter")
            await wait_until(
                pilot, lambda: ("save-key", "openrouter") in fake_backend.calls
            )
            await wait_until(pilot, lambda: not app.operation_busy)

            assert ("save-key", "openrouter") in fake_backend.calls
            assert app.model_lists["openrouter"] == before
            status = app.query_one("#status").render().plain.upper()
            assert "SAVED" in status and "RETAINED" in status

    asyncio.run(run())


@pytest.mark.parametrize(
    ("provider", "dialog_id"),
    [
        ("openrouter", "#api-key-dialog"),
        ("azure", "#azure-dialog"),
    ],
)
def test_ctrl_q_cannot_escape_credential_modal_or_discard_typed_input(
    app_factory,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    dialog_id: str,
):
    app = app_factory(fake_backend)
    exit_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exit_calls.append(args))

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, f"provider:{provider}")
            await settle(pilot)
            await pilot.press("f7")
            await settle(pilot)

            dialog = app.screen.query_one(dialog_id)
            key_field = app.screen.query_one("#api-key-input", Input)
            key_field.focus()
            await pilot.press(*"typed-value")
            await settle(pilot)
            before = key_field.value

            await pilot.press("ctrl+q")
            await settle(pilot)

            assert app.screen.query_one(dialog_id) is dialog
            assert app.screen.query_one("#api-key-input", Input).value == before
            assert before == "typed-value"
            assert not exit_calls
            assert app.launch_codex is False
            assert not any(call[0] == "save-key" for call in fake_backend.calls)

    asyncio.run(run())


def test_switching_to_openai_uses_currently_authenticated_account(
    app_factory, fake_backend: FakeBackend
):
    authenticated = "current@example.invalid"
    fake_backend.config_state = {
        "provider": "openrouter",
        "model": "openrouter/auto",
        "reasoning_effort": "low",
    }
    fake_backend.codex_state = {
        "model_provider": "openrouter",
        "model": "openrouter/auto",
        "model_reasoning_effort": "low",
    }
    fake_backend.auth_state = {"email": authenticated}
    fake_backend["openai_accounts"] = lambda: [
        "stored@example.invalid",
        authenticated,
    ]
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert app.provider == "openrouter"
            assert app.account is None

            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:openai")
            await settle(pilot)

            assert app.provider == "openai"
            assert app.account == authenticated
            assert app.draft.account == authenticated
            assert "PENDING" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_openai_validation_failure_does_not_switch_account(
    app_factory, fake_backend: FakeBackend
):
    original = "tester@example.invalid"
    other = "other@example.invalid"
    fake_backend["openai_accounts"] = lambda: [original, other]

    def reject_model(provider: str, model: str) -> None:
        raise SystemExit(1)

    fake_backend["validate_provider_model"] = reject_model
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, f"account:{other}")
            await settle(pilot)
            await pilot.press("f6")
            await wait_until(pilot, lambda: not app.operation_busy)

            assert fake_backend.auth_state["email"] == original
            assert not any(call[0] == "use-account" for call in fake_backend.calls)
            assert app.query_one("#models").has_focus
            assert "ERROR" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_config_failure_does_not_switch_openai_account(
    app_factory, fake_backend: FakeBackend
):
    original = "tester@example.invalid"
    other = "other@example.invalid"
    fake_backend["openai_accounts"] = lambda: [original, other]

    def reject_update(
        provider: str, model: str, effort: str | None = None
    ) -> None:
        fake_backend.calls.append(("apply-failed", provider, model, effort))
        raise SystemExit(1)

    fake_backend["update_codex_config"] = reject_update
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, f"account:{other}")
            await settle(pilot)
            await pilot.press("f6")
            await wait_until(pilot, lambda: not app.operation_busy)

            account_calls = [
                call for call in fake_backend.calls if call[0] == "use-account"
            ]
            assert account_calls == []
            assert fake_backend.auth_state["email"] == original
            assert app.query_one("#reasoning").has_focus
            assert "ERROR" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_account_failure_rolls_back_the_applied_model_config(
    app_factory, fake_backend: FakeBackend
):
    original = "tester@example.invalid"
    other = "other@example.invalid"
    fake_backend["openai_accounts"] = lambda: [original, other]

    def reject_account(email: str) -> None:
        fake_backend.calls.append(("use-account-failed", email))
        raise SystemExit(1)

    fake_backend["use_openai_account"] = reject_account
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, f"account:{other}")
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            highlight(models, "model:gpt-alpha")
            await settle(pilot)
            await pilot.press("f6")
            await wait_until(pilot, lambda: not app.operation_busy)

            apply_calls = [
                call for call in fake_backend.calls if call[0] == "apply"
            ]
            assert apply_calls[0][1:3] == ("openai", "gpt-alpha")
            assert apply_calls[-1][1:3] == ("openai", "gpt-main")
            assert fake_backend.codex_state["model"] == "gpt-main"
            assert fake_backend.auth_state["email"] == original
            assert app.query_one("#sources").has_focus
            assert "ERROR" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_missing_active_auth_marks_saved_account_out_of_sync_and_reapplies_it(
    app_factory,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
):
    saved = "saved@example.invalid"
    fake_backend.config_state["openai_account"] = saved
    fake_backend.auth_state = {}
    fake_backend["openai_accounts"] = lambda: [saved]
    app = app_factory(fake_backend)
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: None)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert app.account == saved
            assert app.runtime_drift
            assert "OUT OF SYNC" in app.query_one("#status").render().plain.upper()

            await pilot.press("f9")
            await wait_until(
                pilot,
                lambda: ("use-account", saved) in fake_backend.calls,
            )
            await wait_until(pilot, lambda: app.launch_codex)
            assert fake_backend.auth_state["email"] == saved
            assert not app.runtime_drift

    asyncio.run(run())


def test_f6_reconciles_current_openai_account_with_saved_state(
    app_factory, fake_backend: FakeBackend
):
    current = "tester@example.invalid"
    fake_backend.config_state["openai_account"] = "stale@example.invalid"
    fake_backend.auth_state = {"email": current}
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert app.account == current
            assert app.runtime_drift

            await pilot.press("f6")
            await wait_until(pilot, lambda: not app.operation_busy)
            assert fake_backend.config_state["openai_account"] == current
            assert not app.runtime_drift
            assert not app.selection_is_dirty()

    asyncio.run(run())


def test_azure_modal_fits_80x24_and_validates_in_field_order(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:azure")
            await settle(pilot)
            await pilot.press("f7")
            await settle(pilot)

            dialog = app.screen.query_one("#azure-dialog")
            assert dialog.region.right <= 80 and dialog.region.bottom <= 24
            endpoint = app.screen.query_one("#azure-endpoint-input", Input)
            key = app.screen.query_one("#api-key-input", Input)
            save = app.screen.query_one("#api-key-save", Button)
            cancel = app.screen.query_one("#api-key-cancel", Button)
            assert endpoint.has_focus
            await pilot.press("tab", "tab")
            assert save.has_focus
            assert save.styles.background == Color.parse("#ffff00")
            await pilot.press("tab")
            assert cancel.has_focus
            assert cancel.styles.background == Color.parse("#ffff00")
            endpoint.focus()
            await pilot.press("enter")
            assert key.has_focus

            endpoint.value = ""
            key.focus()
            await pilot.press("enter")
            await settle(pilot)
            assert endpoint.has_focus
            assert "Endpoint is required" in app.screen.query_one(
                "#form-error"
            ).render().plain
            assert not any(call[0] == "save-key" for call in fake_backend.calls)

    asyncio.run(run())


def test_help_modal_fits_80x24_scrolls_and_restores_focus(app_factory):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources")
            assert sources.has_focus
            await pilot.press("f1")
            await settle(pilot)
            dialog = app.screen.query_one("#help-dialog")
            assert dialog.region.x >= 0 and dialog.region.y >= 0
            assert dialog.region.right <= 80 and dialog.region.bottom <= 24
            assert dialog.max_scroll_y > 0
            help_text = app.screen.query_one("#help-content").render().plain
            assert "←→" in help_text
            await pilot.press("down", "pageup", "escape")
            await settle(pilot)
            assert sources.has_focus

    asyncio.run(run())


def test_help_uses_available_height_without_scrolling_at_120x40(app_factory):
    app = app_factory()

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await pilot.press("f1")
            await settle(pilot)
            dialog = app.screen.query_one("#help-dialog")
            assert dialog.region.bottom <= 40
            assert dialog.max_scroll_y == 0

    asyncio.run(run())


def test_slow_refresh_is_nonblocking_and_duplicate_refresh_is_suppressed(
    app_factory, fake_backend: FakeBackend
):
    started = threading.Event()
    release = threading.Event()

    def slow_refresh(strict: bool = False) -> bool:
        fake_backend.calls.append(("refresh", "openai", strict))
        started.set()
        assert release.wait(timeout=3), "test did not release refresh worker"
        return True

    fake_backend["refresh_openai_models"] = slow_refresh
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await pilot.press("f5")
            await asyncio.to_thread(started.wait, 1)
            await settle(pilot)
            assert "REFRESH" in app.query_one("#status").render().plain.upper()

            # The UI must still accept navigation while the backend call blocks.
            await pilot.press("right")
            assert app.query_one("#models").has_focus
            await pilot.press("f5")
            await settle(pilot)
            assert [
                call for call in fake_backend.calls if call[:2] == ("refresh", "openai")
            ] == [("refresh", "openai", False)]

            release.set()
            await app.workers.wait_for_complete()
            await settle(pilot)
            assert not app.busy_providers
            assert "ERROR" not in app.query_one("#status").render().plain.upper()

    try:
        asyncio.run(run())
    finally:
        release.set()


def test_failed_refresh_keeps_last_usable_catalog(
    app_factory, fake_backend: FakeBackend
):
    fake_backend["refresh_openai_models"] = lambda strict=False: False
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            before = [option.id for option in models.options]
            await pilot.press("f5")
            await wait_until(
                pilot,
                lambda: "ERROR" in app.query_one("#status").render().plain.upper()
                or "FAILED" in app.query_one("#status").render().plain.upper(),
            )
            assert [option.id for option in models.options] == before

    asyncio.run(run())


def test_details_render_markup_like_and_unicode_metadata_literally(app_factory):
    app = app_factory(refresh_on_start=True)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await app.workers.wait_for_complete()
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            highlight(models, "model:gpt-alpha")
            await wait_until(
                pilot,
                lambda: "gpt-alpha"
                in app.query_one("#model-detail").render().plain,
            )
            detail = app.query_one("#model-detail").render().plain
            assert "Alpha [Preview] Ω" in detail
            assert "gpt-alpha" in detail

    asyncio.run(run())


def test_status_renders_external_markup_characters_literally(
    app_factory, fake_backend: FakeBackend
):
    model = "[bold]literal[/bold]"
    fake_backend.config_state["model"] = model
    fake_backend.codex_state["model"] = model
    fake_backend["OPENAI_FALLBACK_MODELS"].append(model)
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert model in app.query_one("#status").render().plain

    asyncio.run(run())


def test_model_switch_uses_metadata_default_reasoning_instead_of_first_choice(
    app_factory, fake_backend: FakeBackend
):
    fake_backend.openai_catalog["gpt-alpha"]["default_reasoning_level"] = "high"
    app = app_factory(fake_backend, refresh_on_start=True)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await app.workers.wait_for_complete()
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            highlight(models, "model:gpt-alpha")
            await settle(pilot)

            reasoning = app.query_one("#reasoning", OptionList)
            assert app.model == "gpt-alpha"
            assert app.draft.reasoning == "high"
            assert reasoning.highlighted_option is not None
            assert reasoning.highlighted_option.id == "reason:high"
            assert "◆" in option_plain(
                option_by_id(reasoning, "reason:high")
            )

    asyncio.run(run())


def test_azure_shows_all_reasoning_levels_and_defaults_to_low(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:azure")
            await settle(pilot)

            reasoning = app.query_one("#reasoning", OptionList)
            assert app.draft.reasoning == "low"
            assert [option.id for option in reasoning.options] == [
                "reason:low",
                "reason:medium",
                "reason:high",
                "reason:xhigh",
                "reason:max",
                "reason:ultra",
            ]
            assert "◆" in option_plain(option_by_id(reasoning, "reason:low"))

    asyncio.run(run())


def test_azure_apply_updates_codex_provider_model_and_reasoning(
    app_factory, fake_backend: FakeBackend
):
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:azure")
            await settle(pilot)
            await pilot.press("f6")
            await wait_until(pilot, lambda: not app.operation_busy)
            assert fake_backend.codex_state == {
                "model_provider": "azure",
                "model": "azure-gpt",
                "model_reasoning_effort": "low",
            }
            assert ("apply", "azure", "azure-gpt", "low") in fake_backend.calls

    asyncio.run(run())


def test_reasoning_options_are_derived_from_loaded_catalog_without_backend_io(
    app_factory, fake_backend: FakeBackend
):
    def unexpected_reasoning_call(*args: Any, **kwargs: Any) -> None:
        pytest.fail("reasoning choices should not perform backend I/O on the UI loop")

    fake_backend["openai_reasoning_choices"] = unexpected_reasoning_call
    fake_backend["reasoning_choices"] = unexpected_reasoning_call
    fake_backend["openrouter_reasoning_choices"] = unexpected_reasoning_call
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            highlight(models, "model:gpt-alpha")
            await settle(pilot)

            assert [
                option.id for option in app.query_one("#reasoning", OptionList).options
            ] == ["reason:low", "reason:medium", "reason:high"]

    asyncio.run(run())


def test_apply_reloads_backend_normalized_reasoning(
    app_factory, fake_backend: FakeBackend
):
    def normalize_reasoning(
        provider: str, model: str, effort: str | None = None
    ) -> None:
        fake_backend.calls.append(("apply", provider, model, effort))
        fake_backend.config_state = {
            "provider": provider,
            "model": model,
            "reasoning_effort": "medium",
        }
        fake_backend.codex_state = {
            "model_provider": provider,
            "model": model,
            "model_reasoning_effort": "medium",
        }

    fake_backend["update_codex_config"] = normalize_reasoning
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            sources = app.query_one("#sources", OptionList)
            highlight(sources, "provider:opencode-go")
            await settle(pilot)
            assert app.draft.reasoning is None
            await pilot.press("f6")
            await wait_until(
                pilot,
                lambda: any(call[0] == "apply" for call in fake_backend.calls),
            )
            await wait_until(pilot, lambda: not app.operation_busy)
            assert app.active.reasoning == "medium"
            assert app.draft.reasoning == "medium"
            assert not app.selection_is_dirty()

    asyncio.run(run())


def test_launch_stops_when_runtime_remains_out_of_sync(
    app_factory,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
):
    def update_saved_state_only(
        provider: str, model: str, effort: str | None = None
    ) -> None:
        fake_backend.calls.append(("apply", provider, model, effort))
        fake_backend.config_state = {"provider": provider, "model": model}
        if effort:
            fake_backend.config_state["reasoning_effort"] = effort

    fake_backend["update_codex_config"] = update_saved_state_only
    app = app_factory(fake_backend)
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: None)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            models = app.query_one("#models", OptionList)
            highlight(models, "model:gpt-alpha")
            await settle(pilot)
            await pilot.press("f9")
            await wait_until(pilot, lambda: not app.operation_busy)

            assert app.runtime_drift
            assert not app.launch_codex
            status = app.query_one("#status").render().plain.upper()
            assert "ERROR" in status and "OUT OF SYNC" in status

    asyncio.run(run())


def test_runtime_drift_is_reported_without_replacing_active_fallback(
    app_factory, fake_backend: FakeBackend
):
    fake_backend.codex_state = {
        "model_provider": "openai",
        "model": "externally-changed",
        "model_reasoning_effort": "medium",
    }
    app = app_factory(fake_backend)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert app.provider == "openai"
            assert app.model == "externally-changed"
            assert app.selection_is_dirty() is True
            rendered = (
                app.query_one("#status").render().plain
                + app.query_one("#model-detail").render().plain
            ).upper()
            assert "OUT OF SYNC" in rendered
            await pilot.press("f8")
            await settle(pilot)
            assert app.runtime_drift
            assert "OUT OF SYNC" in app.query_one("#status").render().plain.upper()

    asyncio.run(run())


def test_missing_runtime_config_is_out_of_sync_and_f9_applies(
    app_factory,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_backend.codex_state = {}
    app = app_factory(fake_backend)
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: None)

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert app.runtime_drift
            assert "OUT OF SYNC" in app.query_one("#status").render().plain.upper()
            await pilot.press("f9")
            await wait_until(
                pilot,
                lambda: any(call[0] == "apply" for call in fake_backend.calls),
            )
            await wait_until(pilot, lambda: app.launch_codex)
            assert app.launch_codex

    asyncio.run(run())


def test_codex_launch_argv_uses_bypass_and_search_without_resume():
    assert tui.codex_launch_argv("/usr/local/bin/codex") == [
        "/usr/local/bin/codex",
        "--dangerously-bypass-approvals-and-sandbox",
        "--search",
    ]


def test_main_checks_codex_runtime_before_exec(
    monkeypatch: pytest.MonkeyPatch, fake_backend: FakeBackend, tmp_path: Path
):
    calls: list[Any] = []

    class FakeApp:
        launch_codex = True

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self) -> None:
            calls.append("run")

    fake_backend["ensure_codex_runtime_writable"] = lambda: calls.append(
        "preflight"
    )
    monkeypatch.setattr(tui, "BACKEND", fake_backend)
    monkeypatch.setattr(tui.os, "name", "posix")
    monkeypatch.setattr(tui, "CodexSwitchApp", FakeApp)
    monkeypatch.setattr(tui, "codex_launch_argv", lambda: ["/bin/echo", "codex"])

    def fake_execvp(binary: str, argv: list[str]) -> None:
        calls.append(("exec", binary, argv))
        raise SystemExit(0)

    monkeypatch.setattr(tui.os, "execvp", fake_execvp)
    with pytest.raises(SystemExit):
        tui.main()

    assert calls == [
        "run",
        "preflight",
        ("exec", "/bin/echo", ["/bin/echo", "codex"]),
    ]


def test_main_waits_for_codex_subprocess_on_windows(
    monkeypatch: pytest.MonkeyPatch, fake_backend: FakeBackend
):
    calls: list[Any] = []

    class FakeApp:
        launch_codex = True

        def run(self) -> None:
            calls.append("run")

    fake_backend["ensure_codex_runtime_writable"] = lambda: calls.append(
        "preflight"
    )
    monkeypatch.setattr(tui, "BACKEND", fake_backend)
    monkeypatch.setattr(tui, "CodexSwitchApp", FakeApp)
    monkeypatch.setattr(tui, "codex_launch_argv", lambda: ["codex.cmd", "--search"])
    monkeypatch.setattr(tui.os, "name", "nt")
    monkeypatch.setattr(
        tui.subprocess,
        "run",
        lambda argv, **kwargs: calls.append(("run-codex", argv, kwargs)) or tui.subprocess.CompletedProcess(
            argv, 23
        ),
    )
    monkeypatch.setattr(
        tui.os,
        "execvp",
        lambda *args: pytest.fail("Windows launch must not replace the TUI process"),
    )

    assert tui.main() == 23
    assert calls == [
        "run",
        "preflight",
        (
            "run-codex",
            ["codex.cmd", "--search"],
            {
                "env": {"TEST_CODEX_ENV": "1"},
            },
        ),
    ]


def test_windows_launch_uses_native_npm_codex_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    host_path_type = type(tmp_path)
    shim = tmp_path / "codex.cmd"
    native = (
        tmp_path
        / "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64"
        / "vendor/x86_64-pc-windows-msvc/bin/codex.exe"
    )
    native.parent.mkdir(parents=True)
    native.write_bytes(b"")
    monkeypatch.setattr(tui.os, "name", "nt")
    monkeypatch.setattr(tui, "Path", host_path_type)

    assert tui.codex_launch_argv(str(shim))[0] == str(native)


def test_headless_driver_uses_requested_terminal_size(app_factory):
    """Guard the two canonical viewport sizes used by the visual QA checks."""

    async def check(size: tuple[int, int]) -> None:
        app = app_factory()
        async with app.run_test(size=size) as pilot:
            await settle(pilot)
            assert app.screen.size == Size(*size)

    asyncio.run(check((80, 24)))
    asyncio.run(check((120, 40)))
