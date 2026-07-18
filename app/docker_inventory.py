"""Read-only Docker Engine inventory and resource snapshot broker.

The Docker socket is effectively a host-administration API.  This module keeps
that authority behind a deliberately small surface: it discovers only
allowlisted media services from standard Docker metadata, and it only performs
container list, inspect, and
non-streaming stats GET requests. Docker response bodies and connection details are
never included in public errors.
"""

from __future__ import annotations

import copy
import hmac
import http.client
import ipaddress
import json
import os
import re
import socket
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEFAULT_SOCKET_PATH = "/var/run/docker.sock"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_CONTAINER_WORKERS = 8
MAX_BROKER_REQUESTS = 16
SNAPSHOT_CACHE_SECONDS = 5.0

COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
COMPOSE_SERVICE_LABEL = "com.docker.compose.service"
COMPOSE_ONEOFF_LABEL = "com.docker.compose.oneoff"
COMPOSE_SERVER_SERVICE = "server"
UMBRELARR_SERVICE_LABEL = "io.umbrelarr.service"

SERVICE_IDS = (
    "umbrelarr",
    "prowlarr",
    "privado-vpn",
    "flaresolverr",
    "qbittorrent",
    "sabnzbd",
    "sonarr",
    "sonarr-4k",
    "radarr",
    "radarr-4k",
    "lidarr",
    "bazarr",
    "overseerr",
    "profilarr",
    "jellyfin",
    "plex",
)

PROJECT_TO_SERVICE_ID = {
    **{f"umbrel-arr-{service_id}": service_id for service_id in SERVICE_IDS if service_id not in {"jellyfin", "plex"}},
    "jellyfin": "jellyfin",
    "plex": "plex",
}
SERVICE_ID_SET = frozenset(SERVICE_IDS)

_CONTAINER_ID = re.compile(r"^[0-9a-f]{12,64}$")
_API_VERSION = re.compile(r"^[0-9]+\.[0-9]+$")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
_KNOWN_STATES = frozenset({"created", "restarting", "running", "removing", "paused", "exited", "dead"})
_KNOWN_HEALTH = frozenset({"starting", "healthy", "unhealthy"})


class DockerEngineError(RuntimeError):
    """A deliberately non-sensitive Docker Engine failure."""


class UnixHTTPConnection(http.client.HTTPConnection):
    """An HTTP/1.1 connection transported over an AF_UNIX socket."""

    def __init__(self, socket_path: str, timeout: float):
        super().__init__("docker", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(self.socket_path)
        except Exception:
            connection.close()
            raise
        self.sock = connection


class DockerEngineClient:
    """Minimal Docker Engine client with no generic request/proxy method."""

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        *,
        timeout: float = 3.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        connection_factory: Callable[[str, float], Any] | None = None,
    ):
        if socket_path.startswith("unix://"):
            socket_path = socket_path.removeprefix("unix://")
        if not socket_path.startswith("/") or "\x00" in socket_path:
            raise ValueError("Docker socket path must be an absolute Unix path")
        if timeout <= 0:
            raise ValueError("Docker timeout must be positive")
        if max_response_bytes < 1:
            raise ValueError("Docker response limit must be positive")
        self.socket_path = socket_path
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._connection_factory = connection_factory or UnixHTTPConnection
        self._api_version: str | None = None
        self._version_lock = threading.Lock()

    def list_containers(self) -> list[dict[str, Any]]:
        value = self._get_json(f"{self._version_prefix()}/containers/json?all=1")
        if not isinstance(value, list):
            raise DockerEngineError("Docker Engine returned an invalid container list")
        return [item for item in value if isinstance(item, dict)]

    def inspect_container(self, container_id: str) -> dict[str, Any]:
        container_id = self._validated_container_id(container_id)
        value = self._get_json(f"{self._version_prefix()}/containers/{container_id}/json")
        if not isinstance(value, dict):
            raise DockerEngineError("Docker Engine returned invalid container metadata")
        return value

    def container_stats(self, container_id: str) -> dict[str, Any]:
        container_id = self._validated_container_id(container_id)
        # With stream=false Docker waits for a second sample so cpu_stats and
        # precpu_stats form a usable delta. one-shot=true would return sooner,
        # but can leave precpu_stats empty and incorrectly report 0% CPU. The
        # connection timeout still bounds this non-streaming request.
        value = self._get_json(
            f"{self._version_prefix()}/containers/{container_id}/stats?stream=false"
        )
        if not isinstance(value, dict):
            raise DockerEngineError("Docker Engine returned invalid container statistics")
        return value

    @staticmethod
    def _validated_container_id(container_id: str) -> str:
        value = str(container_id).lower()
        if not _CONTAINER_ID.fullmatch(value):
            raise DockerEngineError("Docker Engine returned an invalid container identifier")
        return value

    def _version_prefix(self) -> str:
        if self._api_version is None:
            with self._version_lock:
                if self._api_version is None:
                    value = self._get_json("/version")
                    version = value.get("ApiVersion") if isinstance(value, dict) else None
                    if not isinstance(version, str) or not _API_VERSION.fullmatch(version):
                        raise DockerEngineError("Docker Engine API version is unavailable")
                    self._api_version = version
        return f"/v{self._api_version}"

    def _get_json(self, path: str) -> Any:
        # Paths are constructed exclusively by the three public read methods
        # above.  Refuse characters that could alter the HTTP request line.
        if not path.startswith("/") or any(character in path for character in "\r\n\x00"):
            raise DockerEngineError("Docker Engine request path is invalid")
        connection = None
        try:
            connection = self._connection_factory(self.socket_path, self.timeout)
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "application/json",
                    "Connection": "close",
                    "Host": "docker",
                },
            )
            response = connection.getresponse()
            body = response.read(self.max_response_bytes + 1)
        except (OSError, http.client.HTTPException, TimeoutError):
            raise DockerEngineError("Docker Engine is unavailable") from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        if len(body) > self.max_response_bytes:
            raise DockerEngineError("Docker Engine response exceeded the safe limit")
        if response.status < 200 or response.status >= 300:
            # Never include Docker's response body: daemon errors can contain
            # host paths, registry credentials, or other private metadata.
            raise DockerEngineError(f"Docker Engine request failed with status {response.status}")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DockerEngineError("Docker Engine returned an invalid response") from None


class DockerInventory:
    """Build sanitized snapshots for allowlisted local media services."""

    def __init__(
        self,
        client: DockerEngineClient,
        *,
        now: Callable[[], datetime] | None = None,
    ):
        self.client = client
        self._now = now or (lambda: datetime.now(timezone.utc))

    def snapshot(self) -> dict[str, Any]:
        candidates: dict[str, dict[str, Any]] = {}
        for summary in self.client.list_containers():
            service_id = self._service_id(summary)
            container_id = self._container_id(summary)
            if service_id is None or container_id is None:
                continue
            existing = candidates.get(service_id)
            if existing is None or self._preference(summary) > self._preference(existing):
                candidates[service_id] = summary

        selected = [
            (service_id, candidates[service_id])
            for service_id in SERVICE_IDS
            if service_id in candidates
        ]
        services: dict[str, dict[str, Any]] = {}
        if selected:
            # A non-streaming Docker stats call waits for a comparable CPU
            # sample pair. Collect containers in a small fixed pool so that
            # one sample interval is paid per wave rather than per service.
            # Resolve futures in catalog order to keep the public snapshot
            # deterministic regardless of completion order.
            with ThreadPoolExecutor(
                max_workers=min(MAX_CONTAINER_WORKERS, len(selected)),
                thread_name_prefix="docker-inventory",
            ) as executor:
                futures = {
                    service_id: executor.submit(self._service_snapshot, service_id, summary)
                    for service_id, summary in selected
                }
                for service_id, summary in selected:
                    try:
                        services[service_id] = futures[service_id].result()
                    except Exception:
                        # Isolate unexpected per-container failures without
                        # exposing Docker or host details or dropping healthy
                        # candidates from the same snapshot.
                        services[service_id] = self._unavailable_service(service_id, summary)

        timestamp = self._now()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        updated_at = timestamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return {"updatedAt": updated_at, "services": services}

    def _service_snapshot(
        self,
        service_id: str,
        summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        container_id = self._container_id(summary)
        if container_id is None:
            return self._unavailable_service(service_id, summary)
        try:
            inspected = self.client.inspect_container(container_id)
        except DockerEngineError:
            inspected = {}

        state_data = inspected.get("State") if isinstance(inspected.get("State"), Mapping) else {}
        state = self._state(state_data.get("Status") or summary.get("State"))
        health_data = state_data.get("Health") if isinstance(state_data.get("Health"), Mapping) else {}
        health = self._health(health_data.get("Status"))
        resources = None
        if state == "running":
            try:
                resources = self._resources(self.client.container_stats(container_id))
            except DockerEngineError:
                resources = None

        return {
            "id": service_id,
            "containerId": container_id[:12],
            "name": self._container_name(inspected, summary),
            "state": state,
            "health": health,
            "resources": resources,
        }

    def _unavailable_service(
        self,
        service_id: str,
        summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        container_id = self._container_id(summary) or ""
        return {
            "id": service_id,
            "containerId": container_id[:12],
            "name": self._container_name({}, summary),
            "state": self._state(summary.get("State")),
            "health": "none",
            "resources": None,
        }

    @staticmethod
    def _service_id(summary: Mapping[str, Any]) -> str | None:
        labels = summary.get("Labels")
        labels = labels if isinstance(labels, Mapping) else {}
        if str(labels.get(COMPOSE_ONEOFF_LABEL, "")).casefold() == "true":
            return None

        project = DockerInventory._service_token(labels.get(COMPOSE_PROJECT_LABEL))
        compose_service = DockerInventory._service_token(labels.get(COMPOSE_SERVICE_LABEL))
        known_project = PROJECT_TO_SERVICE_ID.get(project)
        if known_project:
            # The Umbrel app projects contain sidecars. Only their server
            # service represents the managed application.
            return known_project if compose_service == COMPOSE_SERVER_SERVICE else None

        explicit = DockerInventory._service_token(labels.get(UMBRELARR_SERVICE_LABEL))
        if explicit in SERVICE_ID_SET:
            return explicit
        if compose_service in SERVICE_ID_SET:
            return compose_service
        if project in SERVICE_ID_SET and compose_service in {project, COMPOSE_SERVER_SERVICE, None}:
            return project

        image = DockerInventory._service_token(summary.get("Image"), repository=True)
        if image in SERVICE_ID_SET:
            return image
        names = summary.get("Names")
        if isinstance(names, list):
            for name in names:
                candidate = DockerInventory._service_token(name)
                if candidate in SERVICE_ID_SET:
                    return candidate
        return None

    @staticmethod
    def _service_token(value: Any, *, repository: bool = False) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        token = value.strip().lower().removeprefix("/")
        if repository:
            token = token.split("@", 1)[0].rsplit("/", 1)[-1].split(":", 1)[0]
        token = token.replace("_", "-")
        return token if token and _SAFE_NAME.sub("", token) == token else None

    @staticmethod
    def _container_id(summary: Mapping[str, Any]) -> str | None:
        value = summary.get("Id")
        if not isinstance(value, str):
            return None
        value = value.lower()
        return value if _CONTAINER_ID.fullmatch(value) else None

    @staticmethod
    def _preference(summary: Mapping[str, Any]) -> tuple[int, int, str]:
        state = str(summary.get("State", "")).lower()
        created = _nonnegative_int(summary.get("Created"))
        identifier = str(summary.get("Id", ""))
        return (1 if state == "running" else 0, created, identifier)

    @staticmethod
    def _state(value: Any) -> str:
        state = str(value).lower()
        return state if state in _KNOWN_STATES else "unknown"

    @staticmethod
    def _health(value: Any) -> str:
        if value is None:
            return "none"
        health = str(value).lower()
        return health if health in _KNOWN_HEALTH else "unknown"

    @staticmethod
    def _container_name(inspected: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
        value = inspected.get("Name")
        if not isinstance(value, str):
            names = summary.get("Names")
            value = names[0] if isinstance(names, list) and names and isinstance(names[0], str) else ""
        value = value.removeprefix("/")[:128]
        return _SAFE_NAME.sub("-", value).strip("-")

    @staticmethod
    def _resources(stats: Mapping[str, Any]) -> dict[str, Any]:
        cpu_stats = stats.get("cpu_stats") if isinstance(stats.get("cpu_stats"), Mapping) else {}
        previous_cpu = stats.get("precpu_stats") if isinstance(stats.get("precpu_stats"), Mapping) else {}
        cpu_usage = cpu_stats.get("cpu_usage") if isinstance(cpu_stats.get("cpu_usage"), Mapping) else {}
        previous_usage = previous_cpu.get("cpu_usage") if isinstance(previous_cpu.get("cpu_usage"), Mapping) else {}
        current_total = _optional_nonnegative_int(cpu_usage.get("total_usage"))
        previous_total = _optional_nonnegative_int(previous_usage.get("total_usage"))
        current_system = _optional_nonnegative_int(cpu_stats.get("system_cpu_usage"))
        previous_system = _optional_nonnegative_int(previous_cpu.get("system_cpu_usage"))
        # Match the Docker CLI's total-container convention: one fully used
        # logical CPU is 100%, so a multi-threaded container may exceed 100%.
        # Older daemons omit online_cpus; Docker falls back to the per-CPU
        # usage array in that case.
        online_cpus = _optional_nonnegative_int(cpu_stats.get("online_cpus")) or 0
        if online_cpus <= 0:
            per_cpu_usage = cpu_usage.get("percpu_usage")
            online_cpus = len(per_cpu_usage) if isinstance(per_cpu_usage, list) else 0
        cpu_percent = None
        if None not in (current_total, previous_total, current_system, previous_system):
            cpu_delta = max(0, current_total - previous_total)
            system_delta = max(0, current_system - previous_system)
            if system_delta > 0 and online_cpus > 0:
                cpu_percent = round(max(0.0, cpu_delta / system_delta * online_cpus * 100.0), 2)

        memory_stats = stats.get("memory_stats") if isinstance(stats.get("memory_stats"), Mapping) else {}
        memory_used = _optional_nonnegative_int(memory_stats.get("usage"))
        memory_total = _optional_nonnegative_int(memory_stats.get("limit"))
        memory_details = memory_stats.get("stats") if isinstance(memory_stats.get("stats"), Mapping) else {}
        # Docker reports memory working set, not raw cgroup usage. Cgroup v1
        # exposes total_inactive_file while cgroup v2 exposes inactive_file.
        # As in Docker CLI, do not subtract an invalid cache value that is
        # greater than or equal to the reported usage.
        memory = None
        if memory_used is not None and memory_total is not None:
            if "total_inactive_file" in memory_details:
                inactive_cache = _nonnegative_int(memory_details.get("total_inactive_file"))
            else:
                inactive_cache = _nonnegative_int(memory_details.get("inactive_file"))
            if inactive_cache < memory_used:
                memory_used -= inactive_cache
            memory_percent = (
                round(min(100.0, max(0.0, memory_used / memory_total * 100.0)), 2)
                if memory_total else None
            )
            memory = {
                "usedBytes": memory_used,
                "totalBytes": memory_total,
                "percent": memory_percent,
            }

        block_io = None
        block_stats = stats.get("blkio_stats") if isinstance(stats.get("blkio_stats"), Mapping) else {}
        entries = block_stats.get("io_service_bytes_recursive")
        if isinstance(entries, list):
            block_read = 0
            block_write = 0
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                operation = str(entry.get("op", "")).lower()
                if operation == "read":
                    block_read += _nonnegative_int(entry.get("value"))
                elif operation == "write":
                    block_write += _nonnegative_int(entry.get("value"))
            block_io = {"readBytes": block_read, "writeBytes": block_write}

        network = None
        networks = stats.get("networks")
        if isinstance(networks, Mapping):
            network_rx = 0
            network_tx = 0
            for counters in networks.values():
                if not isinstance(counters, Mapping):
                    continue
                network_rx += _nonnegative_int(counters.get("rx_bytes"))
                network_tx += _nonnegative_int(counters.get("tx_bytes"))
            network = {"rxBytes": network_rx, "txBytes": network_tx}

        return {
            "cpuPercent": cpu_percent,
            "onlineCpus": online_cpus or None,
            "cpuCapacityPercent": online_cpus * 100 if online_cpus else None,
            "memory": memory,
            "blockIO": block_io,
            "network": network,
        }


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return None


class SnapshotCache:
    """Single-flight a short-lived snapshot so requests cannot amplify Docker work."""

    def __init__(
        self,
        inventory: DockerInventory,
        *,
        ttl: float = SNAPSHOT_CACHE_SECONDS,
        monotonic: Callable[[], float] | None = None,
    ):
        self.inventory = inventory
        self.ttl = max(0.0, float(ttl))
        self._monotonic = monotonic or time.monotonic
        self._lock = threading.Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0
        self._failed_at: float | None = None

    def snapshot(self) -> dict[str, Any]:
        now = self._monotonic()
        with self._lock:
            if self._cached is not None and now - self._cached_at < self.ttl:
                return copy.deepcopy(self._cached)
            if self._failed_at is not None and now - self._failed_at < self.ttl:
                raise DockerEngineError("Docker inventory is temporarily unavailable")
            try:
                value = self.inventory.snapshot()
            except Exception:
                self._failed_at = self._monotonic()
                raise DockerEngineError("Docker inventory is unavailable") from None
            if not isinstance(value, dict):
                self._failed_at = self._monotonic()
                raise DockerEngineError("Docker inventory returned an invalid snapshot")
            self._cached = copy.deepcopy(value)
            self._cached_at = self._monotonic()
            self._failed_at = None
            return copy.deepcopy(value)


class BrokerHandler(BaseHTTPRequestHandler):
    """Expose one authenticated, non-proxying inventory endpoint."""

    server_version = "UmbrelArrDockerInventory/1.0"

    def log_message(self, _format: str, *_args: Any):
        return

    def do_GET(self):
        if self.path == "/healthz":
            return self._send_json(200, {"ok": True})
        if self.path != "/v1/snapshot":
            return self._send_json(404, {"error": "Not found"})
        token = getattr(self.server, "access_token", None)
        if token is not None and not self._authorized(token):
            return self._send_json(
                401,
                {"error": "Unauthorized"},
                {"WWW-Authenticate": 'Bearer realm="docker-inventory"'},
            )
        try:
            snapshot = self.server.inventory.snapshot()
        except Exception:
            # Do not expose daemon errors, socket paths, container metadata, or
            # unexpected internal exceptions through this privileged boundary.
            return self._send_json(503, {"error": "Docker inventory unavailable"})
        return self._send_json(200, snapshot)

    def do_HEAD(self):
        return self._method_not_allowed()

    def do_POST(self):
        return self._method_not_allowed()

    def do_PUT(self):
        return self._method_not_allowed()

    def do_PATCH(self):
        return self._method_not_allowed()

    def do_DELETE(self):
        return self._method_not_allowed()

    def do_OPTIONS(self):
        return self._method_not_allowed()

    def _authorized(self, token: str) -> bool:
        authorization = self.headers.get("Authorization", "")
        scheme, separator, candidate = authorization.partition(" ")
        return bool(separator) and scheme == "Bearer" and hmac.compare_digest(candidate, token)

    def _method_not_allowed(self):
        return self._send_json(405, {"error": "Method not allowed"}, {"Allow": "GET"})

    def _send_json(self, status: int, value: Any, headers: Mapping[str, str] | None = None):
        body = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Bound concurrent internal requests before they allocate handler threads."""

    daemon_threads = True

    def __init__(self, server_address, handler_class, max_requests=MAX_BROKER_REQUESTS):
        self._request_slots = threading.BoundedSemaphore(max(1, int(max_requests)))
        super().__init__(server_address, handler_class)

    def process_request(self, request, client_address):
        if not self._request_slots.acquire(blocking=False):
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


def make_server(
    host: str,
    port: int,
    inventory: DockerInventory,
    *,
    token: str | None = None,
) -> BoundedThreadingHTTPServer:
    if not token and not _is_loopback_host(host):
        raise ValueError("A Docker inventory token is required for non-loopback bindings")
    server = BoundedThreadingHTTPServer((host, port), BrokerHandler)
    server.inventory = SnapshotCache(inventory)
    server.access_token = token if token else None
    return server


def _is_loopback_host(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _environment_port() -> int:
    raw = os.environ.get("DOCKER_INVENTORY_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw)
    except ValueError:
        raise SystemExit("DOCKER_INVENTORY_PORT must be an integer") from None
    if not 1 <= port <= 65535:
        raise SystemExit("DOCKER_INVENTORY_PORT must be between 1 and 65535")
    return port


def main():
    socket_path = os.environ.get("DOCKER_INVENTORY_SOCKET", DEFAULT_SOCKET_PATH)
    host = os.environ.get("DOCKER_INVENTORY_HOST", DEFAULT_HOST)
    token = os.environ.get("DOCKER_INVENTORY_TOKEN") or None
    if not token and not _is_loopback_host(host):
        raise SystemExit(
            "DOCKER_INVENTORY_TOKEN is required when the broker is not bound to loopback"
        )
    inventory = DockerInventory(DockerEngineClient(socket_path))
    server = make_server(host, _environment_port(), inventory, token=token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
