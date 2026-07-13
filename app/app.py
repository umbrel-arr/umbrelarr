import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dashboard import SERVICE_TITLES, render_page
from reconciler import ReconcileLoop, Reconciler


RECONCILER = Reconciler()
ICON = Path(__file__).with_name("icon.png").read_bytes()


class Handler(BaseHTTPRequestHandler):
    server_version = "UmbrelArr/1.1"

    def log_message(self, _format, *_args):
        return

    def send_body(self, status, content_type, body):
        encoded = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, status, value):
        self.send_body(status, "application/json", json.dumps(value))

    def send_redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        target = urlsplit(self.path)
        path = target.path
        pages = {
            "/": "overview",
            "/index.html": "overview",
            "/setup": "setup",
            "/services": "services",
            "/dependencies": "dependencies",
            "/libraries": "libraries",
            "/activity": "activity",
        }
        if path in pages:
            values = parse_qs(target.query)
            mode = values.get("mode", ["basic"])[0]
            return self.send_body(200, "text/html; charset=utf-8", render_page(pages[path], mode))
        if path == "/settings/media":
            suffix = f"?{target.query}" if target.query else ""
            return self.send_redirect(f"/libraries{suffix}")
        if path.startswith("/services/"):
            service_id = path.removeprefix("/services/").strip("/")
            if service_id in SERVICE_TITLES:
                return self.send_body(200, "text/html; charset=utf-8", render_page("service", service_id=service_id))
        if path == "/icon.png":
            return self.send_body(200, "image/png", ICON)
        if path == "/api/status":
            return self.send_json(200, RECONCILER.runtime.snapshot())
        if path == "/api/setup":
            return self.send_json(200, RECONCILER.setup_snapshot())
        if path == "/api/storage":
            return self.send_json(200, RECONCILER.storage_snapshot())
        if path == "/healthz":
            return self.send_json(200, {"ok": True})
        return self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._same_origin():
            return self.send_json(403, {"error": "Request origin is not allowed"})
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/reconcile":
                self._require_setup()
                started = RECONCILER.reconcile_async()
                return self.send_json(202 if started else 200, {"started": started})
            if path == "/api/setup/detect":
                return self.send_json(200, RECONCILER.detect_apps())
            if path == "/api/setup/confirm":
                values = self._form()
                try:
                    root_ids = json.loads(values.get("rootIds", ["{}"]) [0] or "{}")
                except json.JSONDecodeError as error:
                    raise ValueError("rootIds must be a JSON object") from error
                if not isinstance(root_ids, dict):
                    raise ValueError("rootIds must be a JSON object")
                return self.send_json(202, RECONCILER.confirm_setup(
                    values.get("storageMode", [""])[0],
                    root_ids,
                    values.get("qbittorrentUsername", ["admin"])[0],
                    values.get("qbittorrentTemporaryPassword", [""])[0],
                ))
            if path == "/api/vpn/login":
                self._require_setup()
                values = self._form()
                RECONCILER.save_vpn_login(values.get("username", [""])[0], values.get("password", [""])[0])
                return self.send_json(202, {"accepted": True})
            if path == "/api/storage":
                self._require_setup()
                values = self._form()
                try:
                    root_ids = json.loads(values.get("rootIds", ["{}"]) [0] or "{}")
                except json.JSONDecodeError as error:
                    raise ValueError("rootIds must be a JSON object") from error
                if not isinstance(root_ids, dict):
                    raise ValueError("rootIds must be a JSON object")
                storage = RECONCILER.save_storage(values.get("mode", ["local"])[0], root_ids)
                return self.send_json(200, storage)
            return self.send_json(404, {"error": "Not found"})
        except (ValueError, RuntimeError) as error:
            return self.send_json(400, {"error": RECONCILER._safe_error(error)})

    def _form(self):
        length = int(self.headers.get("Content-Length", "0"))
        return parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)

    def _same_origin(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if not origin:
            return True
        return origin in {f"http://{host}", f"https://{host}"}

    @staticmethod
    def _require_setup():
        if not RECONCILER.ensure_setup_ready():
            raise RuntimeError("Complete explicit setup before changing managed apps")


def main():
    loop = ReconcileLoop(RECONCILER)
    threading.Thread(target=loop.run, name="reconcile-loop", daemon=True).start()
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
