import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from dashboard import PAGE
from reconciler import ReconcileLoop, Reconciler


RECONCILER = Reconciler()


class Handler(BaseHTTPRequestHandler):
    server_version = "UmbrelArr/1.0"

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

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in {"/", "/index.html"}:
            return self.send_body(200, "text/html; charset=utf-8", PAGE)
        if path == "/api/status":
            return self.send_json(200, RECONCILER.runtime.snapshot())
        if path == "/api/storage":
            return self.send_json(200, RECONCILER.storage.snapshot())
        if path == "/healthz":
            return self.send_json(200, {"ok": True})
        return self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._same_origin():
            return self.send_json(403, {"error": "Request origin is not allowed"})
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/reconcile":
                started = RECONCILER.reconcile_async()
                return self.send_json(202 if started else 200, {"started": started})
            if path == "/api/vpn/login":
                values = self._form()
                RECONCILER.save_vpn_login(values.get("username", [""])[0], values.get("password", [""])[0])
                return self.send_json(202, {"accepted": True})
            if path == "/api/storage":
                values = self._form()
                roots = {
                    slug: values.get(slug, [""])[0]
                    for slug in ("sonarr", "sonarr-4k", "radarr", "radarr-4k", "lidarr")
                }
                storage = RECONCILER.save_storage(values.get("mode", ["local"])[0], roots)
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


def main():
    loop = ReconcileLoop(RECONCILER)
    threading.Thread(target=loop.run, name="reconcile-loop", daemon=True).start()
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
