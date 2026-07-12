import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "app"
ROOT = SOURCE.parent
sys.path.insert(0, str(SOURCE))

from dashboard import PAGE
from http_client import Response
from reconciler import Reconciler, Settings
from state import OwnershipState, RuntimeState, ServiceStatus
from storage import NETWORK_ROOTS, StorageSettings


def environment(state_dir):
    values = {
        "STATE_DIR": str(state_dir),
        "DEVICE_DOMAIN_NAME": "umbrel.local",
        "UMBREL_ARR_PRIVADO_VPN_URL": "http://vpn:8080",
        "UMBREL_ARR_FLARESOLVERR_URL": "http://flare:8191",
        "UMBREL_ARR_PROWLARR_URL": "http://prowlarr:9696",
        "UMBREL_ARR_QBITTORRENT_URL": "http://qbit:8080",
        "UMBREL_ARR_SABNZBD_URL": "http://sab:8080",
        "UMBREL_ARR_SONARR_URL": "http://sonarr:8989",
        "UMBREL_ARR_SONARR_4K_URL": "http://sonarr4k:8989",
        "UMBREL_ARR_RADARR_URL": "http://radarr:7878",
        "UMBREL_ARR_RADARR_4K_URL": "http://radarr4k:7878",
        "UMBREL_ARR_BAZARR_URL": "http://bazarr:6767",
        "UMBREL_ARR_OVERSEERR_URL": "http://overseerr:5055",
        "UMBREL_ARR_PROFILARR_URL": "http://profilarr:6868",
        "UMBREL_ARR_LIDARR_URL": "http://lidarr:8686",
        "UMBREL_ARR_PRIVADO_SOCKS_HOST": "vpn",
        "UMBREL_ARR_PRIVADO_SOCKS_PORT": "1080",
    }
    for slug in ("prowlarr", "sabnzbd", "sonarr", "sonarr_4k", "radarr", "radarr_4k", "bazarr", "overseerr", "lidarr"):
        values[f"UMBREL_ARR_{slug.upper()}_API_KEY"] = f"{slug}-key"
    return values


class FakeClient:
    def __init__(self):
        self.calls = []
        self.vpn = {"credentialsConfigured": False, "state": "down"}

    def request(self, method, url, headers=None, body=None, timeout=20):
        self.calls.append(("request", method, url, headers, body))
        return Response(200, {}, b"ok")

    def form(self, method, url, values, headers=None):
        self.calls.append(("form", method, url, headers, values))
        return Response(200, {}, b"{}")

    def json(self, method, url, api_key=None, payload=None, headers=None):
        self.calls.append(("json", method, url, api_key, payload, headers))
        if url.endswith("/api/status"):
            return self.vpn
        return {}


def schema(implementation, fields):
    return {
        "implementation": implementation,
        "implementationName": implementation,
        "configContract": f"{implementation}Settings",
        "fields": [{"name": name, "value": value} for name, value in fields.items()],
        "tags": [],
    }


class StackClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.roots = []
        self.clients = []
        self.tags = []
        self.proxies = []
        self.applications = []
        self.host_config = {"id": 1, "proxyEnabled": False, "proxyType": "http", "proxyHostname": "", "proxyPort": 0, "proxyBypassFilter": "", "proxyBypassLocalAddresses": True}

    def json(self, method, url, api_key=None, payload=None, headers=None):
        self.calls.append(("json", method, url, api_key, payload, headers))
        path = url.split("/api/", 1)[-1]
        if path.endswith("system/status"):
            return {"version": "test"}
        if path.endswith("metadataprofile"):
            return [{"id": 3, "name": "Standard"}]
        if path.endswith("qualityprofile"):
            return [{"id": 4, "name": "Any"}]
        if path.endswith("rootfolder"):
            if method == "POST":
                created = {**payload, "id": len(self.roots) + 1}
                self.roots.append(created)
                return created
            return [dict(item) for item in self.roots]
        if path.endswith("downloadclient/schema"):
            return [
                schema("QBittorrent", {"host": "", "port": 0, "useSsl": False, "urlBase": "", "category": ""}),
                schema("Sabnzbd", {"host": "", "port": 0, "useSsl": False, "urlBase": "", "category": "", "apiKey": ""}),
            ]
        if path.endswith("downloadclient"):
            if method == "POST":
                created = {**payload, "id": len(self.clients) + 1}
                self.clients.append(created)
                return created
            return [dict(item) for item in self.clients]
        if "/downloadclient/" in path and method == "PUT":
            return self._replace(self.clients, payload)
        if path.endswith("config/host"):
            return dict(self.host_config)
        if "/config/host/" in path and method == "PUT":
            self.host_config = dict(payload)
            return self.host_config
        if path.endswith("tag"):
            if method == "POST":
                created = {**payload, "id": len(self.tags) + 1}
                self.tags.append(created)
                return created
            return [dict(item) for item in self.tags]
        if path.endswith("indexerproxy/schema"):
            return [schema("FlareSolverr", {"host": "", "requestTimeout": 0})]
        if path.endswith("indexerproxy"):
            if method == "POST":
                created = {**payload, "id": len(self.proxies) + 1}
                self.proxies.append(created)
                return created
            return [dict(item) for item in self.proxies]
        if "/indexerproxy/" in path and method == "PUT":
            return self._replace(self.proxies, payload)
        if path.endswith("applications/schema"):
            return [schema(name, {"prowlarrUrl": "", "baseUrl": "", "apiKey": ""}) for name in ("Sonarr", "Radarr", "Lidarr")]
        if path.endswith("applications"):
            if method == "POST":
                created = {**payload, "id": len(self.applications) + 1}
                self.applications.append(created)
                return created
            return [dict(item) for item in self.applications]
        if "/applications/" in path and method == "PUT":
            return self._replace(self.applications, payload)
        return super().json(method, url, api_key, payload, headers)

    @staticmethod
    def _replace(collection, payload):
        index = next(index for index, item in enumerate(collection) if item["id"] == payload["id"])
        collection[index] = dict(payload)
        return collection[index]


class ReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = FakeClient()
        self.reconciler = Reconciler(Settings(environment(self.temp.name)), self.client)

    def tearDown(self):
        self.temp.cleanup()

    def test_settings_define_hd_and_4k_instances(self):
        instances = {item.slug: (item.root, item.category, item.is_4k) for item in self.reconciler.arrs}
        self.assertEqual(instances["sonarr"], ("/downloads/shows", "tv", False))
        self.assertEqual(instances["sonarr-4k"], ("/downloads/shows-4k", "tv-4k", True))
        self.assertEqual(instances["radarr"], ("/downloads/movies", "movies", False))
        self.assertEqual(instances["radarr-4k"], ("/downloads/movies-4k", "movies-4k", True))
        self.assertEqual(instances["lidarr"], ("/downloads/music", "music", False))

    def test_vpn_requires_login_then_reports_health(self):
        self.assertEqual(self.reconciler.check_vpn()[0], "action_required")
        self.client.vpn = {"credentialsConfigured": True, "state": "healthy", "publicIp": "203.0.113.7"}
        self.assertIn("203.0.113.7", self.reconciler.check_vpn())

    def test_vpn_login_is_forwarded_without_persistence(self):
        self.reconciler.reconcile_async = lambda: True
        self.reconciler.save_vpn_login("member", "very-secret")
        call = self.client.calls[-1]
        self.assertEqual(call[2], "http://vpn:8080/setup")
        self.assertEqual(call[4]["username"], "member")
        self.assertEqual(call[4]["password"], "very-secret")
        self.assertFalse(any("very-secret" in path.read_text() for path in Path(self.temp.name).glob("**/*") if path.is_file()))

    def test_qbittorrent_configures_proxy_and_five_categories(self):
        detail = self.reconciler.configure_qbittorrent(True)
        forms = [call for call in self.client.calls if call[0] == "form"]
        preferences = json.loads(forms[0][4]["json"])
        categories = [call[4]["category"] for call in forms[1:]]
        self.assertEqual(preferences["proxy_type"], "SOCKS5")
        self.assertEqual(preferences["proxy_ip"], "vpn")
        self.assertEqual(categories, ["movies", "movies-4k", "tv", "tv-4k", "music"])
        self.assertIn("five media categories", detail)

    def test_sabnzbd_uses_current_socks_setting(self):
        self.reconciler.configure_sabnzbd(True)
        forms = [call for call in self.client.calls if call[0] == "form"]
        settings = {call[4].get("keyword"): call[4].get("value") for call in forms}
        self.assertEqual(settings["socks5_proxy_url"], "socks5://vpn:1080")
        self.assertNotIn("socks5_proxy", settings)

    def test_profilarr_forms_are_same_origin(self):
        self.client.json = lambda *_args, **_kwargs: []
        self.assertEqual(self.reconciler.configure_profilarr()[0], "waiting")
        call = next(call for call in self.client.calls if call[0] == "form")
        self.assertEqual(call[3]["Origin"], "http://profilarr:6868")
        self.assertEqual(call[3]["Referer"], "http://profilarr:6868/")

    def test_overseerr_profile_preferences_are_deterministic(self):
        profiles = [{"id": 1, "name": "Any"}, {"id": 2, "name": "1080p Quality HDR"}, {"id": 3, "name": "2160p Quality"}]
        self.assertEqual(self.reconciler._overseerr_profile(profiles, False)["id"], 2)
        self.assertEqual(self.reconciler._overseerr_profile(profiles, True)["id"], 3)

    def test_servarr_configuration_is_idempotent(self):
        client = StackClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        arr = reconciler.arrs[2]
        reconciler.configure_arr(arr)
        reconciler.configure_arr(arr)
        self.assertEqual(client.roots, [{"path": "/downloads/movies", "id": 1}])
        self.assertEqual(len(client.clients), 2)
        self.assertEqual({item["name"] for item in client.clients}, {"Umbrel Arr qBittorrent", "Umbrel Arr SABnzbd"})

    def test_lidarr_root_includes_its_required_name(self):
        client = StackClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        arr = next(item for item in reconciler.arrs if item.slug == "lidarr")
        reconciler.configure_arr(arr)
        self.assertEqual(
            client.roots,
            [{
                "path": "/downloads/music",
                "name": "Music",
                "defaultMetadataProfileId": 3,
                "defaultQualityProfileId": 4,
                "id": 1,
            }],
        )

    def test_prowlarr_configuration_is_idempotent(self):
        client = StackClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.configure_prowlarr(True)
        reconciler.configure_prowlarr(True)
        self.assertEqual(client.tags, [{"label": "flaresolverr", "id": 1}])
        self.assertEqual(len(client.proxies), 1)
        self.assertEqual(client.proxies[0]["tags"], [1])
        self.assertEqual(len(client.applications), 5)
        self.assertTrue(client.host_config["proxyEnabled"])
        self.assertEqual(client.host_config["proxyType"], "socks5")

    def test_errors_redact_secrets(self):
        safe = self.reconciler._safe_error(RuntimeError("password=hunter2 token=abc api_key=xyz"))
        self.assertNotIn("hunter2", safe)
        self.assertNotIn("abc", safe)
        self.assertNotIn("xyz", safe)


class StateTests(unittest.TestCase):
    def test_runtime_state_counts_explicit_unknowns(self):
        state = RuntimeState([ServiceStatus("one", "One"), ServiceStatus("two", "Two")])
        state.set("one", "healthy", "Ready")
        snapshot = state.snapshot()
        self.assertEqual(snapshot["counts"]["healthy"], 1)
        self.assertEqual(snapshot["counts"]["unknown"], 1)

    def test_ownership_state_is_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ownership.json"
            state = OwnershipState(path)
            state.set("resource", {"id": 4})
            self.assertEqual(OwnershipState(path).get("resource"), {"id": 4})

    def test_storage_settings_switch_between_local_and_network_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "storage.json"
            storage = StorageSettings(path)
            self.assertEqual(storage.root("radarr"), "/downloads/movies")
            storage.update("network", {})
            self.assertEqual(storage.root("radarr"), NETWORK_ROOTS["radarr"])
            self.assertEqual(StorageSettings(path).snapshot()["mode"], "network")

    def test_storage_settings_reject_paths_outside_shared_mounts(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = StorageSettings(Path(directory) / "storage.json")
            with self.assertRaisesRegex(ValueError, "/downloads or /network"):
                storage.update("local", {"radarr": "/etc/movies"})


class DashboardTests(unittest.TestCase):
    def test_dashboard_is_operational_and_accessible(self):
        self.assertIn("<table>", PAGE)
        self.assertIn("<title>umbrelarr</title>", PAGE)
        self.assertIn("Privado login required", PAGE)
        self.assertIn("aria-label=\"Stack summary\"", PAGE)
        self.assertIn("Library locations", PAGE)
        self.assertIn("Linked /network storage", PAGE)
        self.assertIn("Reconcile", PAGE)
        self.assertNotIn("linear-gradient", PAGE)
        self.assertNotIn("border-radius:999", PAGE)


class ImageTests(unittest.TestCase):
    def test_image_uses_the_shared_media_uid(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("adduser -S -D -H -u 1000", dockerfile)
        self.assertIn("USER umbrelarr", dockerfile)


if __name__ == "__main__":
    unittest.main()
