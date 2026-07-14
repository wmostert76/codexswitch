import importlib.machinery
import importlib.util
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace


BIN_DIR = Path(__file__).resolve().parents[1] / "bin"


def load_provider_proxy():
    loader = importlib.machinery.SourceFileLoader(
        "codex_provider_proxy_test", str(BIN_DIR / "codex-provider-proxy")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_unified_proxy_loads_isolated_provider_engines():
    proxy = load_provider_proxy()

    assert proxy.OPENCODE_ENGINE.PROVIDER == "opencode-go"
    assert proxy.OPENROUTER_ENGINE.PROVIDER == "openrouter"
    assert sorted(proxy.ROUTES) == ["/azure", "/opencode-go", "/openrouter"]


def test_unified_proxy_routes_provider_prefix_and_preserves_query(monkeypatch):
    proxy = load_provider_proxy()
    received = []

    class FakeHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.path)
            payload = json.dumps({"path": self.path}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    engine = SimpleNamespace(Handler=FakeHandler)
    monkeypatch.setattr(
        proxy,
        "ROUTES",
        {"/opencode-go": engine, "/openrouter": engine, "/azure": engine},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for provider in ("opencode-go", "openrouter"):
            url = (
                f"http://127.0.0.1:{server.server_port}/"
                f"{provider}/v1/models?client=test"
            )
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
    finally:
        server.shutdown()

    assert received == ["/v1/models?client=test"] * 2


def test_unified_health_lists_supported_providers():
    proxy = load_provider_proxy()
    server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/health", timeout=5
        ) as response:
            payload = json.loads(response.read())
    finally:
        server.shutdown()

    assert payload == {
        "ok": True,
        "providers": ["opencode-go", "openrouter", "azure"],
    }


def test_unified_azure_models_route_avoids_catalog_404():
    proxy = load_provider_proxy()
    server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/azure/v1/models",
            timeout=5,
        ) as response:
            payload = json.loads(response.read())
    finally:
        server.shutdown()

    assert payload == {"models": ["gpt-5.6-sol"]}


def test_unified_azure_route_injects_vault_key(tmp_path, monkeypatch):
    received = {}

    class UpstreamHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            received["path"] = self.path
            received["key_present"] = bool(self.headers.get("api-key"))
            length = int(self.headers.get("content-length", "0"))
            self.rfile.read(length)
            payload = json.dumps({"status": "completed"}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    auth_path = tmp_path / ".config/codexswitch/azure/auth.json"
    auth_path.parent.mkdir(parents=True, mode=0o700)
    auth_path.write_text(
        json.dumps(
            {
                "endpoint": (
                    f"http://127.0.0.1:{upstream.server_port}/openai/v1"
                ),
                "api_key": "fixture-secret-never-print",
            }
        )
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    proxy = load_provider_proxy()
    server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            (
                f"http://127.0.0.1:{server.server_port}"
                "/azure/v1/responses"
            ),
            data=json.dumps({"model": "azure-test", "stream": False}).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        upstream.shutdown()

    assert received == {
        "path": "/openai/v1/responses",
        "key_present": True,
    }
