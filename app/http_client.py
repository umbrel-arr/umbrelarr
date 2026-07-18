import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RequestError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


@dataclass
class Response:
    status: int
    headers: object
    body: bytes
    url: str = ""

    def json(self):
        return json.loads(self.body) if self.body else None


class HttpClient:
    def tcp(self, host, port, timeout=3):
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except (OSError, TimeoutError, ValueError) as error:
            raise RequestError(f"Could not reach {host}:{port}: {error}") from error

    def request(self, method, url, headers=None, body=None, timeout=20):
        request = Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return Response(
                    response.status,
                    response.headers,
                    response.read(),
                    response.geturl(),
                )
        except HTTPError as error:
            detail = error.read(512).decode("utf-8", "replace").strip()
            message = f"HTTP {error.code} from {url}"
            if detail:
                message += f": {detail}"
            raise RequestError(message, error.code) from error
        except (URLError, TimeoutError, OSError) as error:
            raise RequestError(f"Could not reach {url}: {error}") from error

    def json(self, method, url, api_key=None, payload=None, headers=None):
        request_headers = {"Accept": "application/json", **(headers or {})}
        if api_key:
            request_headers["X-Api-Key"] = api_key
        body = None
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        return self.request(method, url, request_headers, body).json()

    def form(self, method, url, values, headers=None):
        request_headers = {
            "Accept": "application/json, text/html;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            **(headers or {}),
        }
        body = urlencode(values, doseq=True).encode("utf-8")
        return self.request(method, url, request_headers, body)
