import importlib.machinery
import importlib.util
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BIN_DIR = Path(__file__).resolve().parents[1] / "bin"


def load_azure_proxy():
    loader = importlib.machinery.SourceFileLoader(
        "codex_azure_proxy_test", str(BIN_DIR / "codex-azure-proxy")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_proxy_injects_vault_key_as_azure_api_key(tmp_path, monkeypatch):
    received = {}

    class UpstreamHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            received["path"] = self.path
            received["api_key_present"] = bool(self.headers.get("api-key"))
            length = int(self.headers.get("content-length", "0"))
            received["body"] = json.loads(self.rfile.read(length))
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
                "endpoint": f"http://127.0.0.1:{upstream.server_port}/openai/v1",
                "api_key": "fixture-secret-never-print",
            }
        )
    )
    auth_path.chmod(0o600)
    monkeypatch.setenv("HOME", str(tmp_path))
    proxy = load_azure_proxy()
    server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/v1/responses",
            data=json.dumps({"model": "azure-test", "stream": False}).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert json.loads(response.read()) == {"status": "completed"}
    finally:
        server.shutdown()
        upstream.shutdown()

    assert received == {
        "path": "/openai/v1/responses",
        "api_key_present": True,
        "body": {"model": "azure-test", "stream": False},
    }
