import json
import sys
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(SOURCE))

from docker_inventory import (
    BrokerHandler,
    DockerEngineClient,
    DockerEngineError,
    DockerInventory,
    SnapshotCache,
    make_server,
)


def container_id(character):
    return character * 64


class FakeResponse:
    def __init__(self, status, value):
        self.status = status
        self.body = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")

    def read(self, limit):
        return self.body[:limit]


class FakeConnection:
    def __init__(self, responses, calls):
        self.responses = responses
        self.calls = calls
        self.current = None

    def request(self, method, path, headers=None):
        self.calls.append((method, path, dict(headers or {})))
        self.current = self.responses.pop(0)

    def getresponse(self):
        return self.current

    def close(self):
        return


class FakeConnectionFactory:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.connections = []

    def __call__(self, _socket_path, _timeout):
        connection = FakeConnection(self.responses, self.calls)
        self.connections.append(connection)
        return connection


class FakeDockerClient:
    def __init__(self, containers, inspected=None, stats=None):
        self.containers = containers
        self.inspected = inspected or {}
        self.stats = stats or {}
        self.inspect_calls = []
        self.stats_calls = []

    def list_containers(self):
        return self.containers

    def inspect_container(self, identifier):
        self.inspect_calls.append(identifier)
        value = self.inspected.get(identifier, {})
        if isinstance(value, Exception):
            raise value
        return value

    def container_stats(self, identifier):
        self.stats_calls.append(identifier)
        value = self.stats.get(identifier, {})
        if isinstance(value, Exception):
            raise value
        return value


class FakeInventory:
    def __init__(self, value=None, error=None):
        self.value = value or {"updatedAt": "2026-07-18T12:00:00Z", "services": {}}
        self.error = error
        self.calls = 0

    def snapshot(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


class HandlerHarness(BrokerHandler):
    def __init__(self, inventory, *, token=None, path="/v1/snapshot", headers=None):
        self.server = SimpleNamespace(inventory=inventory, access_token=token)
        self.path = path
        self.headers = headers or {}
        self.result = None

    def _send_json(self, status, value, headers=None):
        self.result = (status, dict(headers or {}), value)
        return self.result


class DockerEngineClientTests(unittest.TestCase):
    def test_negotiates_api_version_once_and_only_uses_get(self):
        identifier = container_id("a")
        factory = FakeConnectionFactory([
            FakeResponse(200, {"ApiVersion": "1.47"}),
            FakeResponse(200, [{"Id": identifier}]),
            FakeResponse(200, {"Id": identifier}),
            FakeResponse(200, {"cpu_stats": {}}),
            FakeResponse(200, []),
        ])
        client = DockerEngineClient("/test/docker.sock", connection_factory=factory)

        self.assertEqual(client.list_containers(), [{"Id": identifier}])
        self.assertEqual(client.inspect_container(identifier), {"Id": identifier})
        self.assertEqual(client.container_stats(identifier), {"cpu_stats": {}})
        self.assertEqual(client.list_containers(), [])

        self.assertEqual(
            [(method, path) for method, path, _headers in factory.calls],
            [
                ("GET", "/version"),
                ("GET", "/v1.47/containers/json?all=1"),
                ("GET", f"/v1.47/containers/{identifier}/json"),
                ("GET", f"/v1.47/containers/{identifier}/stats?stream=false"),
                ("GET", "/v1.47/containers/json?all=1"),
            ],
        )
        self.assertTrue(all(call[2]["Host"] == "docker" for call in factory.calls))

    def test_stats_waits_for_docker_cpu_sample_pair_without_streaming(self):
        identifier = container_id("a")
        factory = FakeConnectionFactory([
            FakeResponse(200, {"ApiVersion": "1.47"}),
            FakeResponse(200, {
                "cpu_stats": {"cpu_usage": {"total_usage": 200}},
                "precpu_stats": {"cpu_usage": {"total_usage": 100}},
            }),
        ])
        client = DockerEngineClient(
            "/test/docker.sock",
            timeout=3.0,
            connection_factory=factory,
        )

        client.container_stats(identifier)

        method, path, _headers = factory.calls[-1]
        self.assertEqual(method, "GET")
        self.assertEqual(path, f"/v1.47/containers/{identifier}/stats?stream=false")
        self.assertNotIn("one-shot", path)

    def test_rejects_arbitrary_container_ids_before_request(self):
        factory = FakeConnectionFactory([])
        client = DockerEngineClient("/test/docker.sock", connection_factory=factory)

        for identifier in ("../containers/json", "anything", "a" * 65, "a" * 11, "abc\r\nDELETE /containers/x"):
            with self.subTest(identifier=identifier):
                with self.assertRaises(DockerEngineError):
                    client.inspect_container(identifier)
                with self.assertRaises(DockerEngineError):
                    client.container_stats(identifier)
        self.assertEqual(factory.calls, [])

    def test_redacts_docker_error_response_body(self):
        factory = FakeConnectionFactory([
            FakeResponse(200, {"ApiVersion": "1.47"}),
            FakeResponse(500, b'{"message":"secret=/host/private/path"}'),
        ])
        client = DockerEngineClient("/test/docker.sock", connection_factory=factory)

        with self.assertRaises(DockerEngineError) as raised:
            client.list_containers()
        self.assertNotIn("secret", str(raised.exception))
        self.assertNotIn("private", str(raised.exception))
        self.assertIn("status 500", str(raised.exception))

    def test_rejects_invalid_version_and_oversized_response(self):
        invalid = FakeConnectionFactory([FakeResponse(200, {"ApiVersion": "../../../socket"})])
        with self.assertRaises(DockerEngineError):
            DockerEngineClient("/test/docker.sock", connection_factory=invalid).list_containers()

        oversized = FakeConnectionFactory([FakeResponse(200, b"0123456789")])
        client = DockerEngineClient(
            "/test/docker.sock",
            max_response_bytes=4,
            connection_factory=oversized,
        )
        with self.assertRaisesRegex(DockerEngineError, "safe limit"):
            client.list_containers()


class DockerInventoryTests(unittest.TestCase):
    def test_maps_only_known_server_projects_and_sanitizes_resources(self):
        prowlarr_id = container_id("a")
        older_prowlarr_id = container_id("b")
        jellyfin_id = container_id("c")
        ignored_id = container_id("d")
        malformed_id = "not-a-container-id"
        labels = lambda project, service="server": {
            "com.docker.compose.project": project,
            "com.docker.compose.service": service,
        }
        containers = [
            {"Id": older_prowlarr_id, "State": "exited", "Created": 99, "Labels": labels("umbrel-arr-prowlarr")},
            {"Id": prowlarr_id, "State": "running", "Created": 5, "Labels": labels("umbrel-arr-prowlarr")},
            {"Id": jellyfin_id, "State": "exited", "Created": 8, "Labels": labels("jellyfin"), "Names": ["/jellyfin_server"]},
            {"Id": ignored_id, "State": "running", "Labels": labels("umbrel-arr-unknown")},
            {"Id": container_id("e"), "State": "running", "Labels": labels("umbrel-arr-radarr", "worker")},
            {
                "Id": container_id("g"),
                "State": "running",
                "Labels": {
                    **labels("umbrel-arr-sonarr"),
                    "com.docker.compose.oneoff": "True",
                },
            },
            {"Id": malformed_id, "State": "running", "Labels": labels("umbrel-arr-sonarr")},
            {"Id": container_id("f"), "State": "running", "Labels": {}},
        ]
        inspected = {
            prowlarr_id: {"Name": "/prowlarr secret/name", "State": {"Status": "running", "Health": {"Status": "healthy"}}},
            jellyfin_id: {"Name": "/jellyfin", "State": {"Status": "exited", "Health": {"Status": "unhealthy"}}},
        }
        stats = {
            prowlarr_id: {
                "cpu_stats": {"cpu_usage": {"total_usage": 350}, "system_cpu_usage": 2000, "online_cpus": 8},
                "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
                "memory_stats": {"usage": 512, "limit": 2048},
                "blkio_stats": {"io_service_bytes_recursive": [
                    {"op": "Read", "value": 10},
                    {"op": "read", "value": 15},
                    {"op": "Write", "value": 20},
                    {"op": "Sync", "value": 999},
                ]},
                "networks": {
                    "default": {"rx_bytes": 100, "tx_bytes": 200},
                    "vpn": {"rx_bytes": 300, "tx_bytes": 400},
                },
                "name": "must-not-leak",
                "env": ["TOKEN=must-not-leak"],
            }
        }
        client = FakeDockerClient(containers, inspected, stats)
        inventory = DockerInventory(
            client,
            now=lambda: datetime(2026, 7, 18, 12, 34, 56, tzinfo=timezone.utc),
        )

        snapshot = inventory.snapshot()

        self.assertEqual(snapshot["updatedAt"], "2026-07-18T12:34:56Z")
        self.assertEqual(set(snapshot["services"]), {"prowlarr", "jellyfin"})
        self.assertCountEqual(client.inspect_calls, [prowlarr_id, jellyfin_id])
        self.assertEqual(client.stats_calls, [prowlarr_id])

        prowlarr = snapshot["services"]["prowlarr"]
        self.assertEqual(prowlarr["containerId"], "a" * 12)
        self.assertEqual(prowlarr["name"], "prowlarr-secret-name")
        self.assertEqual(prowlarr["state"], "running")
        self.assertEqual(prowlarr["health"], "healthy")
        self.assertEqual(prowlarr["resources"], {
            "cpuPercent": 200.0,
            "onlineCpus": 8,
            "cpuCapacityPercent": 800,
            "memory": {"usedBytes": 512, "totalBytes": 2048, "percent": 25.0},
            "blockIO": {"readBytes": 25, "writeBytes": 20},
            "network": {"rxBytes": 400, "txBytes": 600},
        })
        self.assertNotIn("env", json.dumps(snapshot))
        self.assertNotIn("TOKEN", json.dumps(snapshot))

        jellyfin = snapshot["services"]["jellyfin"]
        self.assertEqual(jellyfin["state"], "exited")
        self.assertEqual(jellyfin["health"], "unhealthy")
        self.assertIsNone(jellyfin["resources"])

    def test_discovers_supported_services_from_standard_docker_metadata(self):
        containers = [
            {
                "Id": container_id("1"), "State": "running",
                "Labels": {
                    "com.docker.compose.project": "media",
                    "com.docker.compose.service": "sonarr",
                },
            },
            {
                "Id": container_id("2"), "State": "running",
                "Labels": {
                    "com.docker.compose.project": "radarr-4k",
                    "com.docker.compose.service": "server",
                },
            },
            {
                "Id": container_id("3"), "State": "running", "Labels": {},
                "Image": "lscr.io/linuxserver/bazarr:latest",
            },
            {
                "Id": container_id("4"), "State": "running", "Labels": {},
                "Names": ["/qbittorrent"],
            },
            {
                "Id": container_id("5"), "State": "running",
                "Labels": {"io.umbrelarr.service": "overseerr"},
            },
            {
                "Id": container_id("6"), "State": "running", "Labels": {},
                "Image": "example.invalid/unrelated:latest", "Names": ["/unrelated"],
            },
        ]
        client = FakeDockerClient(containers)

        services = DockerInventory(client).snapshot()["services"]

        self.assertEqual(
            set(services),
            {"sonarr", "radarr-4k", "bazarr", "qbittorrent", "overseerr"},
        )
        self.assertNotIn("unrelated", services)

    def test_exact_service_matching_does_not_guess_from_similar_names(self):
        containers = [
            {
                "Id": container_id("7"), "State": "running", "Labels": {},
                "Image": "example.invalid/sonarr-helper:latest",
                "Names": ["/my-sonarr-copy"],
            },
            {
                "Id": container_id("8"), "State": "running",
                "Labels": {
                    "com.docker.compose.project": "media",
                    "com.docker.compose.service": "prowlarr-helper",
                },
            },
        ]

        services = DockerInventory(FakeDockerClient(containers)).snapshot()["services"]

        self.assertEqual(services, {})

    def test_collects_independent_candidates_concurrently_in_catalog_order(self):
        prowlarr_id = container_id("a")
        lidarr_id = container_id("b")
        labels = lambda project: {
            "com.docker.compose.project": project,
            "com.docker.compose.service": "server",
        }

        class ConcurrentClient(FakeDockerClient):
            def __init__(self):
                super().__init__([
                    {"Id": lidarr_id, "State": "running", "Labels": labels("umbrel-arr-lidarr")},
                    {"Id": prowlarr_id, "State": "running", "Labels": labels("umbrel-arr-prowlarr")},
                ])
                self.barrier = threading.Barrier(2)
                self.lock = threading.Lock()
                self.active = 0
                self.max_active = 0

            def inspect_container(self, identifier):
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                try:
                    self.barrier.wait(timeout=1)
                    return {"State": {"Status": "running", "Health": {"Status": "healthy"}}}
                finally:
                    with self.lock:
                        self.active -= 1

            def container_stats(self, identifier):
                if identifier == prowlarr_id:
                    raise DockerEngineError("isolated stats failure")
                return {
                    "cpu_stats": {
                        "cpu_usage": {"total_usage": 200},
                        "system_cpu_usage": 200,
                        "online_cpus": 2,
                    },
                    "precpu_stats": {
                        "cpu_usage": {"total_usage": 100},
                        "system_cpu_usage": 100,
                    },
                }

        client = ConcurrentClient()

        services = DockerInventory(client).snapshot()["services"]

        self.assertEqual(list(services), ["prowlarr", "lidarr"])
        self.assertEqual(client.max_active, 2)
        self.assertIsNone(services["prowlarr"]["resources"])
        self.assertEqual(services["lidarr"]["resources"]["cpuPercent"], 200.0)
        self.assertEqual(services["lidarr"]["health"], "healthy")

    def test_cpu_uses_docker_total_container_semantics_and_counters_are_nonnegative(self):
        resources = DockerInventory._resources({
            "cpu_stats": {
                "cpu_usage": {"total_usage": 500},
                "system_cpu_usage": 200,
                "online_cpus": 2,
            },
            "precpu_stats": {"cpu_usage": {"total_usage": 0}, "system_cpu_usage": 100},
            "memory_stats": {"usage": 300, "limit": 100},
            "blkio_stats": {"io_service_bytes_recursive": [{"op": "Read", "value": -4}]},
            "networks": {"default": {"rx_bytes": -1, "tx_bytes": "invalid"}},
        })

        self.assertEqual(resources["cpuPercent"], 1000.0)
        self.assertEqual(resources["onlineCpus"], 2)
        self.assertEqual(resources["cpuCapacityPercent"], 200)
        self.assertEqual(resources["memory"]["percent"], 100.0)
        self.assertEqual(resources["blockIO"]["readBytes"], 0)
        self.assertEqual(resources["network"], {"rxBytes": 0, "txBytes": 0})

    def test_cpu_falls_back_to_per_cpu_usage_count_for_older_daemons(self):
        resources = DockerInventory._resources({
            "cpu_stats": {
                "cpu_usage": {"total_usage": 300, "percpu_usage": [100, 100, 100, 0]},
                "system_cpu_usage": 1200,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 800,
            },
        })

        self.assertEqual(resources["cpuPercent"], 200.0)
        self.assertEqual(resources["onlineCpus"], 4)
        self.assertEqual(resources["cpuCapacityPercent"], 400)

    def test_memory_reports_working_set_for_cgroup_v1_and_v2(self):
        cases = (
            ({"total_inactive_file": 256, "inactive_file": 999}, 768, 37.5),
            ({"inactive_file": 128}, 896, 43.75),
            ({"total_inactive_file": 1024}, 1024, 50.0),
        )

        for memory_details, expected_used, expected_percent in cases:
            with self.subTest(memory_details=memory_details):
                resources = DockerInventory._resources({
                    "memory_stats": {
                        "usage": 1024,
                        "limit": 2048,
                        "stats": memory_details,
                    },
                })

                self.assertEqual(resources["memory"], {
                    "usedBytes": expected_used,
                    "totalBytes": 2048,
                    "percent": expected_percent,
                })

    def test_missing_metrics_are_unavailable_but_reported_zeroes_remain_zero(self):
        missing = DockerInventory._resources({})
        self.assertEqual(missing, {
            "cpuPercent": None,
            "onlineCpus": None,
            "cpuCapacityPercent": None,
            "memory": None,
            "blockIO": None,
            "network": None,
        })

        zero = DockerInventory._resources({
            "cpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 200,
                "online_cpus": 2,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 100,
            },
            "memory_stats": {"usage": 0, "limit": 1024, "stats": {}},
            "blkio_stats": {"io_service_bytes_recursive": []},
            "networks": {},
        })
        self.assertEqual(zero["cpuPercent"], 0.0)
        self.assertEqual(zero["memory"], {
            "usedBytes": 0, "totalBytes": 1024, "percent": 0.0,
        })
        self.assertEqual(zero["blockIO"], {"readBytes": 0, "writeBytes": 0})
        self.assertEqual(zero["network"], {"rxBytes": 0, "txBytes": 0})

    def test_inspect_and_stats_failures_do_not_leak_or_drop_installed_service(self):
        identifier = container_id("a")
        client = FakeDockerClient(
            [{
                "Id": identifier,
                "State": "running",
                "Labels": {
                    "com.docker.compose.project": "umbrel-arr-sonarr",
                    "com.docker.compose.service": "server",
                },
            }],
            inspected={identifier: DockerEngineError("secret inspect body")},
            stats={identifier: DockerEngineError("secret stats body")},
        )

        service = DockerInventory(client).snapshot()["services"]["sonarr"]

        self.assertEqual(service["state"], "running")
        self.assertEqual(service["health"], "none")
        self.assertIsNone(service["resources"])
        self.assertNotIn("error", service)


class BrokerHandlerTests(unittest.TestCase):
    @staticmethod
    def request(inventory, method, path, headers=None, token=None):
        handler = HandlerHarness(inventory, token=token, path=path, headers=headers)
        getattr(handler, f"do_{method}")()
        return handler.result

    def test_optional_bearer_auth_and_successful_snapshot(self):
        inventory = FakeInventory()

        status, headers, body = self.request(inventory, "GET", "/v1/snapshot", token="correct-token")
        self.assertEqual(status, 401)
        self.assertEqual(headers["WWW-Authenticate"], 'Bearer realm="docker-inventory"')
        self.assertEqual(body, {"error": "Unauthorized"})

        status, _headers, _body = self.request(
            inventory,
            "GET",
            "/v1/snapshot",
            {"Authorization": "Bearer wrong-token"},
            token="correct-token",
        )
        self.assertEqual(status, 401)

        status, headers, body = self.request(
            inventory,
            "GET",
            "/v1/snapshot",
            {"Authorization": "Bearer correct-token"},
            token="correct-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, inventory.value)
        self.assertEqual(inventory.calls, 1)

        open_inventory = FakeInventory()
        self.assertEqual(self.request(open_inventory, "GET", "/v1/snapshot")[0], 200)

    def test_health_check_is_safe_and_does_not_touch_docker(self):
        inventory = FakeInventory(error=DockerEngineError("Docker is unavailable"))

        status, headers, body = self.request(
            inventory,
            "GET",
            "/healthz",
            token="correct-token",
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers, {})
        self.assertEqual(body, {"ok": True})
        self.assertEqual(inventory.calls, 0)

    def test_non_loopback_broker_binding_requires_a_token(self):
        with self.assertRaisesRegex(ValueError, "token is required"):
            make_server("0.0.0.0", 8765, FakeInventory())

        with patch("docker_inventory.BoundedThreadingHTTPServer") as server_factory:
            server_factory.return_value = SimpleNamespace()
            server = make_server(
                "0.0.0.0", 8765, FakeInventory(), token="shared-secret",
            )
            self.assertEqual(server.access_token, "shared-secret")

        with patch("docker_inventory.BoundedThreadingHTTPServer") as server_factory:
            server_factory.return_value = SimpleNamespace()
            server = make_server("127.0.0.1", 8765, FakeInventory())
            self.assertIsNone(server.access_token)

    def test_never_proxies_arbitrary_paths_queries_or_mutation_verbs(self):
        inventory = FakeInventory()

        for method, path, expected in (
            ("GET", "/v1/snapshot/prowlarr", 404),
            ("GET", "/v1/snapshot?container=prowlarr", 404),
            ("GET", "/containers/json", 404),
            ("GET", "/v1.47/containers/abc/json", 404),
            ("POST", "/v1/snapshot", 405),
            ("PUT", "/v1/snapshot", 405),
            ("PATCH", "/v1/snapshot", 405),
            ("DELETE", "/v1/snapshot", 405),
            ("OPTIONS", "/v1/snapshot", 405),
        ):
            with self.subTest(method=method, path=path):
                status, headers, _body = self.request(inventory, method, path)
                self.assertEqual(status, expected)
                if expected == 405:
                    self.assertEqual(headers["Allow"], "GET")
        self.assertEqual(inventory.calls, 0)

    def test_broker_redacts_inventory_errors(self):
        inventory = FakeInventory(error=DockerEngineError("secret=/host/private/docker.sock"))

        status, _headers, body = self.request(inventory, "GET", "/v1/snapshot")

        self.assertEqual(status, 503)
        self.assertEqual(body, {"error": "Docker inventory unavailable"})
        self.assertNotIn("secret", json.dumps(body))
        self.assertNotIn("private", json.dumps(body))

    def test_snapshot_cache_single_flights_concurrent_requests_and_expires(self):
        class SlowInventory(FakeInventory):
            def __init__(self):
                super().__init__()
                self.started = threading.Event()
                self.release = threading.Event()

            def snapshot(self):
                self.calls += 1
                self.started.set()
                self.release.wait(timeout=1)
                return self.value

        clock = [0.0]
        inventory = SlowInventory()
        cache = SnapshotCache(inventory, ttl=5, monotonic=lambda: clock[0])
        results = []
        first = threading.Thread(target=lambda: results.append(cache.snapshot()))
        second = threading.Thread(target=lambda: results.append(cache.snapshot()))
        first.start()
        self.assertTrue(inventory.started.wait(timeout=1))
        second.start()
        inventory.release.set()
        first.join(timeout=1)
        second.join(timeout=1)

        self.assertEqual(inventory.calls, 1)
        self.assertEqual(len(results), 2)
        results[0]["services"]["mutated"] = {}
        self.assertNotIn("mutated", results[1]["services"])

        clock[0] = 6.0
        cache.snapshot()
        self.assertEqual(inventory.calls, 2)

        failed = FakeInventory(error=DockerEngineError("private daemon detail"))
        failure_cache = SnapshotCache(failed, ttl=5, monotonic=lambda: clock[0])
        with self.assertRaisesRegex(DockerEngineError, "unavailable"):
            failure_cache.snapshot()
        with self.assertRaisesRegex(DockerEngineError, "temporarily unavailable"):
            failure_cache.snapshot()
        self.assertEqual(failed.calls, 1)
        clock[0] = 12.0
        with self.assertRaisesRegex(DockerEngineError, "unavailable"):
            failure_cache.snapshot()
        self.assertEqual(failed.calls, 2)


if __name__ == "__main__":
    unittest.main()
