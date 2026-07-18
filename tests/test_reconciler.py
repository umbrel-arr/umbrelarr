import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


SOURCE = Path(__file__).resolve().parents[1] / "app"
ROOT = SOURCE.parent
sys.path.insert(0, str(SOURCE))

from dashboard import PAGE, render_page
from api_keys import ApiKeyResolver
from catalog import (
    CORE_MODULES, SERVICE_MODULES, dependencies_for, normalize_modules,
    validate_modules,
)
from http_client import RequestError, Response
from reconciler import (
    DEPENDENCIES, MODULE_CATALOG_MARKER_TAG, MODULE_MARKER_PREFIX,
    PROFILARR_SYNC_MARKER_TAG, REQUIRED_APPS, VPN_PROVIDER_MARKER_PREFIX,
    SETUP_MARKER_TAG, SETUP_READY_MARKER_TAG, Reconciler, Settings,
)
from state import RuntimeState, ServiceStatus
from storage import LIBRARY_DEFINITIONS, LOCAL_ROOTS, NETWORK_ROOTS, StorageSettings


def environment(_state_dir=None):
    values = {
        "DEVICE_DOMAIN_NAME": "umbrel.local",
        "UMBREL_ARR_ENABLED_SERVICES": ",".join(REQUIRED_APPS),
        "UMBREL_ARR_VPN_PROVIDER": "privado",
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
        "UMBREL_ARR_JELLYFIN_URL": "http://jellyfin:8096",
        "UMBREL_ARR_PLEX_URL": "http://plex:32400",
        "UMBREL_ARR_PRIVADO_SOCKS_HOST": "vpn",
        "UMBREL_ARR_PRIVADO_SOCKS_PORT": "1080",
        "UMBREL_ARR_QBITTORRENT_PASSWORD": "umbrel-password",
    }
    for slug in ("prowlarr", "sabnzbd", "sonarr", "sonarr_4k", "radarr", "radarr_4k", "bazarr", "overseerr", "lidarr", "jellyfin", "plex"):
        values[f"UMBREL_ARR_{slug.upper()}_API_KEY"] = f"{slug}-key"
    return values


class FakeClient:
    def __init__(self):
        self.calls = []
        self.vpn = {"credentialsConfigured": False, "state": "down"}
        self.tags = []
        self.roots = {}
        self.filesystems = {}

    def request(self, method, url, headers=None, body=None, timeout=20):
        self.calls.append(("request", method, url, headers, body))
        return Response(200, {}, b"ok")

    def tcp(self, host, port, timeout=3):
        self.calls.append(("tcp", host, port, timeout))
        return True

    def form(self, method, url, values, headers=None):
        self.calls.append(("form", method, url, headers, values))
        if url.endswith("/api/v2/auth/login"):
            return Response(200, {"Set-Cookie": "SID=test-session; HttpOnly; path=/"}, b"Ok.")
        return Response(200, {}, b"{}")

    def json(self, method, url, api_key=None, payload=None, headers=None):
        self.calls.append(("json", method, url, api_key, payload, headers))
        if url.endswith("/api/status"):
            return self.vpn
        if method == "DELETE" and "/api/v1/tag/" in url:
            tag_id = int(url.rsplit("/", 1)[-1])
            self.tags = [item for item in self.tags if item.get("id") != tag_id]
            return {}
        if url.endswith("/api/v1/tag"):
            if method == "POST":
                item = {**payload, "id": len(self.tags) + 1}
                self.tags.append(item)
                return item
            return [dict(item) for item in self.tags]
        if "/filesystem?" in url:
            target = urlsplit(url)
            host = url.split("/api/", 1)[0]
            path = parse_qs(target.query).get("path", ["/"])[0]
            value = self.filesystems.get(host, {}).get(path)
            if isinstance(value, Exception):
                raise value
            if value is None:
                value = {
                    "parent": None if path == "/" else str(Path(path).parent),
                    "directories": [],
                }
            return {
                **value,
                "directories": [dict(item) for item in value.get("directories", [])],
            }
        if "/api/" in url and url.endswith("/rootfolder"):
            host = url.split("/api/", 1)[0]
            roots = self.roots.setdefault(host, [])
            if method == "POST":
                item = {**payload, "id": len(roots) + 1}
                roots.append(item)
                return item
            return [dict(item) for item in roots]
        if url.endswith("/metadataprofile"):
            return [{"id": 3, "name": "Standard"}]
        if url.endswith("/qualityprofile"):
            return [{"id": 4, "name": "Any"}]
        return {}


class DockerBrokerClient(FakeClient):
    def __init__(self, snapshot=None, error=None):
        super().__init__()
        self.docker_snapshot = snapshot or {"updatedAt": 100, "services": {}}
        self.docker_error = error

    def json(self, method, url, api_key=None, payload=None, headers=None):
        if url == "http://docker-inventory:8765/v1/snapshot":
            self.calls.append(("json", method, url, api_key, payload, headers))
            if self.docker_error:
                raise self.docker_error
            return json.loads(json.dumps(self.docker_snapshot))
        return super().json(method, url, api_key, payload, headers)


class FailingTagDeleteClient(FakeClient):
    def json(self, method, url, api_key=None, payload=None, headers=None):
        if method == "DELETE" and "/api/v1/tag/" in url:
            raise RequestError("Prowlarr marker update failed", 503)
        return super().json(method, url, api_key, payload, headers)


class QbitAuthClient(FakeClient):
    def __init__(
        self, active_password="temporary-password", allow_unauthenticated=False,
        rejected_login_status=None, session_cookie_name="SID",
    ):
        super().__init__()
        self.active_password = active_password
        self.allow_unauthenticated = allow_unauthenticated
        self.rejected_login_status = rejected_login_status
        self.session_cookie_name = session_cookie_name
        self.preferences = {"web_ui_domain_list": "existing.example"}

    def request(self, method, url, headers=None, body=None, timeout=20):
        if url.endswith("/api/v2/app/version"):
            self.calls.append(("request", method, url, headers, body))
            if self.allow_unauthenticated or (headers or {}).get("Cookie") == "SID=test-session":
                return Response(200, {}, b"5.0.0")
            raise RequestError("HTTP 403", 403)
        return super().request(method, url, headers, body, timeout)

    def form(self, method, url, values, headers=None):
        self.calls.append(("form", method, url, headers, values))
        if url.endswith("/api/v2/auth/login"):
            if values["password"] != self.active_password:
                if self.rejected_login_status:
                    raise RequestError("Unauthorized", self.rejected_login_status)
                return Response(200, {}, b"Fails.")
            return Response(
                200,
                {"Set-Cookie": f"{self.session_cookie_name}=test-session; HttpOnly; path=/"},
                b"Ok.",
            )
        if url.endswith("/api/v2/app/setPreferences"):
            changed = json.loads(values["json"])
            self.preferences.update(changed)
            if changed.get("web_ui_password"):
                self.active_password = changed["web_ui_password"]
            return Response(200, {}, b"")
        return Response(200, {}, b"{}")

    def json(self, method, url, api_key=None, payload=None, headers=None):
        if url.endswith("/api/v2/app/preferences"):
            self.calls.append(("json", method, url, api_key, payload, headers))
            return dict(self.preferences)
        return super().json(method, url, api_key, payload, headers)


class ProfilarrClient(FakeClient):
    def __init__(self, fail_sync_id=None):
        super().__init__()
        self.fail_sync_id = fail_sync_id
        self.instances = [
            {"id": index + 1, "name": name}
            for index, name in enumerate(("Sonarr", "Sonarr 4K", "Radarr", "Radarr 4K"))
        ]

    def json(self, method, url, api_key=None, payload=None, headers=None):
        if url.endswith("/api/v1/status"):
            return {"ok": True}
        if url.endswith("/api/v1/databases"):
            return [{"id": 1, "name": "Dictionarry", "repository_url": "https://github.com/Dictionarry-Hub/database"}]
        if url.endswith("/api/v1/arr"):
            return [dict(item) for item in self.instances]
        return super().json(method, url, api_key, payload, headers)

    def form(self, method, url, values, headers=None):
        if "/sync?/syncQualityProfiles" in url and self.fail_sync_id is not None:
            instance_id = int(url.split("/arr/", 1)[1].split("/", 1)[0])
            if instance_id == self.fail_sync_id:
                raise RequestError("sync failed", 500)
        return super().form(method, url, values, headers)


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
                schema("QBittorrent", {"host": "", "port": 0, "useSsl": False, "urlBase": "", "category": "", "username": "", "password": ""}),
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


class MediaServerClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.jellyfin_folders = [{"Name": "Personal Movies", "Locations": ["/personal"]}]
        self.plex_sections = [
            {"key": "90", "title": "Personal Movies", "Location": [{"path": "/personal"}]},
        ]

    def json(self, method, url, api_key=None, payload=None, headers=None):
        self.calls.append(("json", method, url, api_key, payload, headers))
        target = urlsplit(url)
        if target.path == "/Library/VirtualFolders":
            if method == "POST":
                values = parse_qs(target.query)
                self.jellyfin_folders.append({"Name": values["name"][0], "Locations": []})
                return None
            return [dict(item) for item in self.jellyfin_folders]
        if target.path == "/Library/VirtualFolders/Paths" and method == "POST":
            folder = next(item for item in self.jellyfin_folders if item["Name"] == payload["Name"])
            folder.setdefault("Locations", []).append(payload["Path"])
            return None
        if target.path == "/library/sections":
            if method == "POST":
                values = parse_qs(target.query)
                self.plex_sections.append({
                    "key": str(len(self.plex_sections) + 1),
                    "title": values["name"][0],
                    "Location": [{"path": values["locations"][0]}],
                })
                return None
            return {"MediaContainer": {"Directory": [dict(item) for item in self.plex_sections]}}
        return super().json(method, url, api_key, payload, headers)


class JellyfinBootstrapClient(FakeClient):
    def __init__(
        self, keys=None, administrator=True, reject_login=False,
        fail_key_list=False, fail_logout=False,
    ):
        super().__init__()
        self.keys = [dict(item) for item in (keys or [])]
        self.administrator = administrator
        self.reject_login = reject_login
        self.fail_key_list = fail_key_list
        self.fail_logout = fail_logout
        self.admin_token = "private-admin-session"
        self.created = 0
        self.logged_out = 0

    def json(self, method, url, api_key=None, payload=None, headers=None):
        self.calls.append(("json", method, url, api_key, payload, headers))
        path = urlsplit(url).path
        if path == "/Users/AuthenticateByName":
            if self.reject_login:
                raise RequestError(
                    "password=private-password token=private-admin-session", 401,
                )
            return {"AccessToken": self.admin_token}
        if path == "/Users/Me":
            return {"Policy": {"IsAdministrator": self.administrator}}
        if path == "/Auth/Keys":
            if method == "POST":
                self.created += 1
                self.keys.append({
                    "Name": "umbrelarr",
                    "AccessToken": f"dedicated-key-{self.created}",
                })
                return None
            if self.fail_key_list:
                raise RequestError("token=private-admin-session upstream failed", 503)
            return {"Items": [dict(item) for item in self.keys]}
        if path == "/System/Info":
            token = (headers or {}).get("X-Emby-Token", "")
            valid = {item.get("AccessToken") for item in self.keys}
            if token not in valid:
                raise RequestError("token=rejected-private-key", 401)
            return {"Version": "10.11"}
        if path == "/Sessions/Logout":
            self.logged_out += 1
            if self.fail_logout:
                raise RequestError("logout failed", 503)
            return None
        return super().json(method, url, api_key, payload, headers)


class AllServicesClient(StackClient):
    """Stateful native-API simulator for the complete supported service fleet."""

    def __init__(self):
        super().__init__()
        self.arr_roots = {}
        self.arr_clients = {}
        self.preferences = {"web_ui_domain_list": "existing.example"}
        self.profilarr_databases = [{
            "id": 1,
            "name": "Dictionarry",
            "repository_url": "https://github.com/Dictionarry-Hub/database",
        }]
        self.profilarr_instances = []
        self.overseerr_servers = {"sonarr": [], "radarr": []}
        self.jellyfin_folders = []
        self.plex_sections = []

    def request(self, method, url, headers=None, body=None, timeout=20):
        self.calls.append(("request", method, url, headers, body))
        if "/api?" in url and "mode=version" in url:
            return Response(200, {}, b'{"version":"4.5.0"}')
        return Response(200, {}, b"ok")

    def form(self, method, url, values, headers=None):
        self.calls.append(("form", method, url, headers, values))
        if url.endswith("/api/v2/auth/login"):
            return Response(
                200,
                {"Set-Cookie": "SID=all-services-session; HttpOnly; path=/"},
                b"Ok.",
            )
        if url.endswith("/api/v2/app/setPreferences"):
            self.preferences.update(json.loads(values["json"]))
            return Response(200, {}, b"")
        if url.endswith("/api") and values.get("mode") == "get_config":
            return Response(
                200, {},
                b'{"config":{"misc":{"host_whitelist":"sab,localhost"}}}',
            )
        if url.endswith("/arr/new"):
            if not any(item["name"] == values["name"] for item in self.profilarr_instances):
                self.profilarr_instances.append({
                    "id": len(self.profilarr_instances) + 1,
                    "name": values["name"],
                })
            return Response(200, {}, b"{}")
        return Response(200, {}, b"{}")

    def json(self, method, url, api_key=None, payload=None, headers=None):
        target = urlsplit(url)
        path = target.path
        self.calls.append(("json", method, url, api_key, payload, headers))
        if path == "/api/status":
            return {
                "credentialsConfigured": True,
                "state": "healthy",
                "publicIp": "203.0.113.10",
            }
        if path == "/v1" and method == "POST":
            return {"status": "ok", "sessions": []}
        if path == "/api/v2/app/preferences":
            return dict(self.preferences)
        if target.hostname in {"sonarr", "sonarr4k", "radarr", "radarr4k", "lidarr"}:
            route = path.split("/api/", 1)[-1]
            roots = self.arr_roots.setdefault(target.hostname, [])
            clients = self.arr_clients.setdefault(target.hostname, [])
            if route.endswith("system/status"):
                return {"version": "test"}
            if route.endswith("metadataprofile"):
                return [{"id": 3, "name": "Standard"}]
            if route.endswith("qualityprofile"):
                return [{"id": 4, "name": "Any"}]
            if route.endswith("rootfolder"):
                if method == "POST":
                    created = {**(payload or {}), "id": len(roots) + 1}
                    roots.append(created)
                    return dict(created)
                return [dict(item) for item in roots]
            if route.endswith("downloadclient/schema"):
                return [
                    schema("QBittorrent", {
                        "host": "", "port": 0, "useSsl": False,
                        "urlBase": "", "category": "", "username": "",
                        "password": "",
                    }),
                    schema("Sabnzbd", {
                        "host": "", "port": 0, "useSsl": False,
                        "urlBase": "", "category": "", "apiKey": "",
                    }),
                ]
            if route.endswith("downloadclient"):
                if method == "POST":
                    created = {**(payload or {}), "id": len(clients) + 1}
                    clients.append(created)
                    return dict(created)
                return [dict(item) for item in clients]
            if "/downloadclient/" in route and method == "PUT":
                return self._replace(clients, payload)
        if target.hostname == "profilarr":
            if path == "/api/v1/status":
                return {"ok": True}
            if path == "/api/v1/databases":
                return [dict(item) for item in self.profilarr_databases]
            if path == "/api/v1/arr":
                return [dict(item) for item in self.profilarr_instances]
        if target.hostname == "overseerr":
            if path == "/api/v1/settings/public":
                return {"initialized": True}
            if path == "/api/v1/settings/main":
                return {"applicationTitle": "Overseerr"}
            for kind in ("sonarr", "radarr"):
                route = f"/api/v1/settings/{kind}"
                if path == f"{route}/test":
                    is_4k = str((payload or {}).get("hostname", "")).endswith("4k")
                    if kind == "sonarr":
                        root = "/downloads/shows-4k" if is_4k else "/downloads/shows"
                    else:
                        root = "/downloads/movies-4k" if is_4k else "/downloads/movies"
                    return {
                        "rootFolders": [{"id": 1, "path": root}],
                        "profiles": [
                            {"id": 1, "name": "1080p Quality HDR"},
                            {"id": 2, "name": "2160p Quality"},
                        ],
                        "languageProfiles": [{"id": 1, "name": "English"}],
                    }
                if path == route:
                    if method == "POST":
                        created = {
                            **(payload or {}),
                            "id": len(self.overseerr_servers[kind]) + 1,
                        }
                        self.overseerr_servers[kind].append(created)
                        return dict(created)
                    return [dict(item) for item in self.overseerr_servers[kind]]
                if path.startswith(f"{route}/") and method == "PUT":
                    server_id = int(path.rsplit("/", 1)[-1])
                    replacement = {**(payload or {}), "id": server_id}
                    index = next(
                        index for index, item in enumerate(self.overseerr_servers[kind])
                        if item["id"] == server_id
                    )
                    self.overseerr_servers[kind][index] = replacement
                    return dict(replacement)
        if target.hostname == "jellyfin":
            if path == "/System/Info":
                return {"Version": "10.11"}
            if path == "/Library/VirtualFolders":
                if method == "POST":
                    values = parse_qs(target.query)
                    self.jellyfin_folders.append({
                        "Name": values["name"][0],
                        "Locations": [],
                    })
                    return None
                return [dict(item) for item in self.jellyfin_folders]
            if path == "/Library/VirtualFolders/Paths" and method == "POST":
                folder = next(
                    item for item in self.jellyfin_folders
                    if item["Name"] == payload["Name"]
                )
                if payload["Path"] not in folder["Locations"]:
                    folder["Locations"].append(payload["Path"])
                return None
        if target.hostname == "plex" and path == "/library/sections":
            if method == "POST":
                values = parse_qs(target.query)
                self.plex_sections.append({
                    "key": str(len(self.plex_sections) + 1),
                    "title": values["name"][0],
                    "Location": [{"path": values["locations"][0]}],
                })
                return None
            return {
                "MediaContainer": {
                    "Directory": [dict(item) for item in self.plex_sections],
                },
            }
        # The parent implementation records calls too; remove this one so
        # assertions continue to represent one outbound API call per request.
        self.calls.pop()
        return super().json(method, url, api_key, payload, headers)


class ReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = FakeClient()
        self.reconciler = Reconciler(Settings(environment(self.temp.name)), self.client)

    def tearDown(self):
        self.temp.cleanup()

    def confirmed_reconciler(self, modules, provider="direct", client=None):
        client = client or FakeClient()
        labels = [
            SETUP_MARKER_TAG,
            SETUP_READY_MARKER_TAG,
            MODULE_CATALOG_MARKER_TAG,
            f"{VPN_PROVIDER_MARKER_PREFIX}{provider}",
            *(f"{MODULE_MARKER_PREFIX}{slug}" for slug in modules),
        ]
        client.tags.extend(
            {"id": index + 1, "label": label}
            for index, label in enumerate(labels)
        )
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(reconciler.ensure_setup_ready())
        reconciler.reconcile_async = lambda: True
        return reconciler, client

    def jellyfin_bootstrap_reconciler(self, client, jellyfin_environment_key=""):
        values = environment(self.temp.name)
        values["UMBREL_ARR_JELLYFIN_API_KEY"] = jellyfin_environment_key
        reconciler = Reconciler(Settings(values), client)
        snapshot = reconciler.select_and_detect(
            ["prowlarr", "sonarr", "jellyfin"], "direct",
        )
        jellyfin = next(item for item in snapshot["apps"] if item["id"] == "jellyfin")
        return reconciler, snapshot, jellyfin

    def test_settings_define_hd_and_4k_instances(self):
        instances = {item.slug: (item.root, item.category, item.is_4k) for item in self.reconciler.arrs}
        self.assertEqual(instances["sonarr"], ("/downloads/shows", "tv", False))
        self.assertEqual(instances["sonarr-4k"], ("/downloads/shows-4k", "tv-4k", True))
        self.assertEqual(instances["radarr"], ("/downloads/movies", "movies", False))
        self.assertEqual(instances["radarr-4k"], ("/downloads/movies-4k", "movies-4k", True))
        self.assertEqual(instances["lidarr"], ("/downloads/music", "music", False))

    def test_fresh_install_starts_with_only_required_services_and_direct_networking(self):
        settings = Settings({})
        reconciler = Reconciler(settings, FakeClient())

        self.assertFalse(settings.modules_configured)
        self.assertEqual(settings.enabled_modules, CORE_MODULES)
        self.assertEqual(settings.vpn_provider_id, "direct")
        services = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }
        self.assertEqual(set(services), CORE_MODULES)
        self.assertEqual(services["umbrelarr"]["status"], "action_required")
        self.assertEqual(services["prowlarr"]["status"], "waiting")
        self.assertEqual(services["prowlarr"]["checked_at"], 0)
        self.assertEqual(services["prowlarr"]["checks"], [])

    def test_complete_catalog_sets_up_and_reconciles_idempotently(self):
        selected = {module.id for module in SERVICE_MODULES}
        values = environment(self.temp.name)
        values["UMBREL_ARR_ENABLED_SERVICES"] = ",".join(sorted(selected))
        client = AllServicesClient()
        reconciler = Reconciler(Settings(values), client)

        detected = reconciler.select_and_detect(selected, "privado")

        self.assertEqual(set(detected["enabledServices"]), selected)
        self.assertEqual(detected["requiredCount"], len(selected) - 1)
        self.assertEqual(detected["detectedCount"], len(selected) - 1)
        self.assertTrue(detected["canConfirm"])
        self.assertTrue(all(item["reachable"] for item in detected["apps"]))
        self.assertTrue(all(item["credentials"] for item in detected["apps"]))

        reconciler.reconcile_async = lambda: True
        connected = reconciler.confirm_setup(
            "local",
            enabled_services=selected,
            vpn_provider="privado",
        )
        self.assertTrue(connected["confirmed"])
        self.assertEqual(connected["phase"], "confirmed")

        reconciler.reconcile()
        first = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }
        self.assertEqual(set(first), selected)
        self.assertEqual(
            {slug: item["status"] for slug, item in first.items()},
            {slug: "healthy" for slug in selected},
        )

        managed_counts = {
            "roots": sum(len(items) for items in client.arr_roots.values()),
            "downloadClients": sum(len(items) for items in client.arr_clients.values()),
            "prowlarrApplications": len(client.applications),
            "prowlarrProxies": len(client.proxies),
            "profilarrInstances": len(client.profilarr_instances),
            "overseerrServers": sum(len(items) for items in client.overseerr_servers.values()),
            "jellyfinLibraries": len(client.jellyfin_folders),
            "plexLibraries": len(client.plex_sections),
        }
        self.assertEqual(managed_counts, {
            "roots": 5,
            "downloadClients": 10,
            "prowlarrApplications": 5,
            "prowlarrProxies": 1,
            "profilarrInstances": 4,
            "overseerrServers": 4,
            "jellyfinLibraries": 5,
            "plexLibraries": 5,
        })

        reconciler.reconcile()
        second = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }
        self.assertEqual(
            {slug: item["status"] for slug, item in second.items()},
            {slug: "healthy" for slug in selected},
        )
        self.assertEqual(
            {
                "roots": sum(len(items) for items in client.arr_roots.values()),
                "downloadClients": sum(len(items) for items in client.arr_clients.values()),
                "prowlarrApplications": len(client.applications),
                "prowlarrProxies": len(client.proxies),
                "profilarrInstances": len(client.profilarr_instances),
                "overseerrServers": sum(len(items) for items in client.overseerr_servers.values()),
                "jellyfinLibraries": len(client.jellyfin_folders),
                "plexLibraries": len(client.plex_sections),
            },
            managed_counts,
        )

    def test_dashboard_does_not_present_catalog_defaults_as_local_services(self):
        reconciler = Reconciler(Settings({}), FakeClient())

        snapshot = reconciler.dashboard_snapshot()

        self.assertEqual([item["id"] for item in snapshot["services"]], ["umbrelarr"])
        self.assertEqual(snapshot["inventory"]["mode"], "direct")
        self.assertFalse(snapshot["inventory"]["configured"])
        self.assertEqual(snapshot["inventory"]["discoveredCount"], 0)

    def test_dashboard_shows_an_explicit_direct_service_without_docker_inventory(self):
        settings = Settings({
            "UMBREL_ARR_PROWLARR_URL": "http://prowlarr:9696",
            "UMBREL_ARR_PROWLARR_API_KEY": "prowlarr-key",
        })
        reconciler = Reconciler(settings, FakeClient())

        snapshot = reconciler.dashboard_snapshot()

        services = {item["id"]: item for item in snapshot["services"]}
        self.assertEqual(set(services), {"umbrelarr", "prowlarr"})
        self.assertEqual(services["prowlarr"]["discoverySource"], "direct")
        self.assertTrue(services["prowlarr"]["managed"])

    def test_setup_snapshot_exposes_direct_connection_state_without_secrets(self):
        reconciler = Reconciler(Settings({}), FakeClient())

        snapshot = reconciler.setup_snapshot()
        prowlarr = next(item for item in snapshot["modules"] if item["id"] == "prowlarr")
        flaresolverr = next(
            item for item in snapshot["modules"] if item["id"] == "flaresolverr"
        )

        self.assertNotIn("installedAppUrl", snapshot)
        self.assertEqual(prowlarr["connectionUrl"], "http://umbrel.local:30982")
        self.assertFalse(prowlarr["connectionConfigured"])
        self.assertFalse(prowlarr["credentialConfigured"])
        self.assertEqual(prowlarr["credentialSource"], "missing")
        self.assertEqual(
            prowlarr["apiKeyEnvironmentVariable"],
            "UMBREL_ARR_PROWLARR_API_KEY",
        )
        self.assertFalse(prowlarr["environmentCredentialConfigured"])
        self.assertNotIn("apiKey", prowlarr)
        self.assertFalse(flaresolverr["requires_api_key"])
        self.assertNotIn("apiKeyEnvironmentVariable", flaresolverr)
        self.assertNotIn("credentialSource", flaresolverr)
        self.assertNotIn("credentialConfigured", flaresolverr)
        self.assertNotIn("environmentCredentialConfigured", flaresolverr)

    def test_setup_snapshot_reports_configured_direct_connection_without_key_value(self):
        reconciler = Reconciler(
            Settings({
                "UMBREL_ARR_PROWLARR_URL": "http://prowlarr:9696",
                "UMBREL_ARR_PROWLARR_API_KEY": "private-key",
            }),
            FakeClient(),
        )

        snapshot = reconciler.setup_snapshot()
        prowlarr = next(item for item in snapshot["modules"] if item["id"] == "prowlarr")

        self.assertEqual(prowlarr["connectionUrl"], "http://prowlarr:9696")
        self.assertTrue(prowlarr["connectionConfigured"])
        self.assertTrue(prowlarr["credentialConfigured"])
        self.assertEqual(prowlarr["credentialSource"], "environment")
        self.assertTrue(prowlarr["environmentCredentialConfigured"])
        self.assertNotIn("private-key", str(snapshot))

    def test_platform_login_redirect_requires_a_direct_connection(self):
        class UmbrelProxyClient(FakeClient):
            def request(self, method, url, headers=None, body=None, timeout=20):
                self.calls.append(("request", method, url, headers, body))
                return Response(
                    200,
                    {},
                    b"Umbrel login",
                    "http://umbrel.local:2000/?origin=host&app=umbrel-arr-prowlarr",
                )

        settings = Settings({})
        reconciler = Reconciler(settings, UmbrelProxyClient())

        self.assertEqual(settings.url("prowlarr"), "http://umbrel.local:30982")
        self.assertFalse(settings.url_is_configured("prowlarr"))
        snapshot = reconciler.detect_apps()
        prowlarr = snapshot["apps"][0]
        self.assertTrue(prowlarr["reachable"])
        self.assertTrue(prowlarr["detected"])
        self.assertFalse(prowlarr["credentials"])
        self.assertEqual(prowlarr["action"], "direct_connection_required")
        self.assertIn("platform login", prowlarr["detail"])
        self.assertFalse(snapshot["canConfirm"])

    def test_local_discovery_uses_a_direct_api_endpoint_when_available(self):
        settings = Settings({"UMBREL_ARR_PROWLARR_API_KEY": "prowlarr-key"})
        reconciler = Reconciler(settings, FakeClient())

        snapshot = reconciler.detect_apps()
        prowlarr = snapshot["apps"][0]
        self.assertEqual(settings.url("prowlarr"), "http://umbrel.local:30982")
        self.assertTrue(prowlarr["reachable"])
        self.assertTrue(prowlarr["credentials"])
        self.assertEqual(prowlarr["action"], "none")
        self.assertTrue(snapshot["canConfirm"])

    def test_private_service_url_overrides_external_discovery_address(self):
        settings = Settings({
            "UMBREL_ARR_PROWLARR_URL": "http://umbrel-arr-prowlarr_server_1:9696/",
        })

        self.assertTrue(settings.url_is_configured("prowlarr"))
        self.assertEqual(
            settings.url("prowlarr"),
            "http://umbrel-arr-prowlarr_server_1:9696",
        )

    def test_base_url_changes_default_service_links_without_overriding_service_urls(self):
        local = Settings({"UMBREL_ARR_BASE_URL": "http://localhost/"})
        self.assertEqual(local.base_url, "http://localhost")
        self.assertEqual(local.device_domain, "localhost")
        self.assertEqual(local.url("prowlarr"), "http://localhost:30982")
        self.assertEqual(local.external_url("sabnzbd"), "http://localhost:30984")

        umbrel = Settings({"UMBREL_ARR_BASE_URL": "https://umbrel.local"})
        self.assertEqual(umbrel.url("prowlarr"), "https://umbrel.local:30982")

        overridden = Settings({
            "UMBREL_ARR_BASE_URL": "http://localhost",
            "UMBREL_ARR_PROWLARR_URL": "http://prowlarr:9696/",
        })
        self.assertEqual(overridden.url("prowlarr"), "http://prowlarr:9696")
        self.assertEqual(
            overridden.external_url("prowlarr"),
            "http://localhost:30982",
        )

    def test_base_url_rejects_ambiguous_or_unsafe_values(self):
        invalid = (
            "localhost",
            "file:///tmp/services",
            "http://user:secret@localhost",
            "http://localhost:8080",
            "http://localhost/services",
            "http://localhost?service=prowlarr",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "UMBREL_ARR_BASE_URL"):
                    Settings({"UMBREL_ARR_BASE_URL": value})

    def test_direct_connection_draft_is_used_without_exposing_the_api_key(self):
        settings = Settings({})
        client = FakeClient()
        reconciler = Reconciler(settings, client)

        snapshot = reconciler.select_and_detect(
            ["prowlarr"],
            "direct",
            {"prowlarr": {
                "url": "http://prowlarr:9696/",
                "apiKey": "direct-key",
                "credentialSource": "ui",
            }},
        )

        self.assertEqual(settings.url("prowlarr"), "http://prowlarr:9696")
        self.assertEqual(settings.key("prowlarr"), "direct-key")
        self.assertTrue(snapshot["canConfirm"])
        prowlarr = next(item for item in snapshot["modules"] if item["id"] == "prowlarr")
        self.assertEqual(prowlarr["credentialSource"], "ui")
        self.assertFalse(prowlarr["environmentCredentialConfigured"])
        self.assertNotIn("direct-key", str(snapshot))
        self.assertTrue(any(
            call[0] == "json"
            and call[2] == "http://prowlarr:9696/api/v1/system/status"
            and call[3] == "direct-key"
            for call in client.calls
        ))

    def test_environment_source_replaces_a_ui_key_without_exposing_either_value(self):
        settings = Settings({"UMBREL_ARR_PROWLARR_API_KEY": "environment-key"})
        settings.apply_connections(
            {"prowlarr": {
                "url": "http://prowlarr:9696",
                "apiKey": "ui-key",
                "credentialSource": "ui",
            }},
            {"umbrelarr", "prowlarr"},
        )
        self.assertEqual(settings.key("prowlarr"), "ui-key")

        settings.apply_connections(
            {"prowlarr": {
                "url": "http://prowlarr:9696",
                "credentialSource": "environment",
            }},
            {"umbrelarr", "prowlarr"},
        )

        self.assertEqual(settings.key("prowlarr"), "environment-key")
        metadata = settings.credential_metadata("prowlarr")
        self.assertEqual(metadata["credentialSource"], "environment")
        self.assertNotIn("environment-key", str(metadata))
        self.assertNotIn("ui-key", str(metadata))

    def test_canceling_setup_forgets_direct_connection_draft(self):
        settings = Settings({})
        reconciler = Reconciler(settings, FakeClient())
        reconciler.select_and_detect(
            ["prowlarr"],
            "direct",
            {"prowlarr": {"url": "http://prowlarr:9696", "apiKey": "direct-key"}},
        )

        reconciler.cancel_selection_change()

        self.assertEqual(settings.url("prowlarr"), "http://umbrel.local:30982")
        self.assertEqual(settings.key("prowlarr"), "")

    def test_direct_connection_validation_is_atomic(self):
        settings = Settings({})

        with self.assertRaisesRegex(ValueError, "without credentials"):
            settings.apply_connections(
                {"prowlarr": {"url": "http://user:secret@prowlarr:9696", "apiKey": "key"}},
                {"umbrelarr", "prowlarr"},
            )

        self.assertEqual(
            settings.connection_overrides(),
            {"urls": {}, "keys": {}, "keySources": {}},
        )

        with self.assertRaisesRegex(ValueError, "selected service"):
            settings.apply_connections(
                {"sonarr": {"url": "http://sonarr:8989", "apiKey": "key"}},
                {"umbrelarr", "prowlarr"},
            )

        with self.assertRaisesRegex(ValueError, "Do not submit an API key"):
            settings.apply_connections(
                {"prowlarr": {
                    "url": "http://prowlarr:9696",
                    "apiKey": "key",
                    "credentialSource": "environment",
                }},
                {"umbrelarr", "prowlarr"},
            )

    def test_docker_inventory_drives_installed_detection_and_resources(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
            "UMBREL_ARR_DOCKER_BROKER_TOKEN": "inventory-secret",
        })
        client = DockerBrokerClient({
            "updatedAt": 1_700_000_000,
            "services": {
                "umbrelarr": {
                    "id": "umbrelarr",
                    "containerId": "manager123456",
                    "name": "umbrel-arr-umbrelarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": {
                        "cpuPercent": 12.5,
                        "onlineCpus": 4,
                        "cpuCapacityPercent": 400,
                        "memory": {
                            "usedBytes": 128,
                            "totalBytes": 1024,
                            "percent": 12.5,
                        },
                        "blockIO": {"readBytes": 10, "writeBytes": 20},
                        "network": {"rxBytes": 30, "txBytes": 40},
                    },
                },
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "prowlarr1234",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": {
                        "cpuPercent": 7.25,
                        "onlineCpus": 8,
                        "cpuCapacityPercent": 800,
                        "memory": {
                            "usedBytes": 256,
                            "totalBytes": 2048,
                            "percent": 12.5,
                        },
                        "blockIO": {"readBytes": 50, "writeBytes": 60},
                        "network": {"rxBytes": 70, "txBytes": 80},
                    },
                },
            },
        })
        reconciler = Reconciler(Settings(values), client)

        snapshot = reconciler.detect_apps()

        prowlarr = snapshot["apps"][0]
        self.assertTrue(prowlarr["detected"])
        self.assertTrue(prowlarr["reachable"])
        self.assertEqual(prowlarr["container"]["state"], "running")
        self.assertEqual(prowlarr["action"], "none")
        module = next(item for item in snapshot["modules"] if item["id"] == "prowlarr")
        self.assertTrue(module["installed"])
        self.assertEqual(module["container"]["health"], "healthy")
        services = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }
        self.assertEqual(services["prowlarr"]["resources"]["cpu"]["percent"], 7.25)
        self.assertEqual(services["prowlarr"]["resources"]["cpu"]["onlineCpus"], 8)
        self.assertEqual(services["prowlarr"]["resources"]["cpu"]["capacityPercent"], 800)
        self.assertEqual(services["prowlarr"]["resources"]["blockIo"]["writeBytes"], 60)
        broker_call = next(
            call for call in client.calls
            if call[0] == "json" and call[2].endswith("/v1/snapshot")
        )
        self.assertEqual(broker_call[1], "GET")
        self.assertEqual(
            broker_call[5]["Authorization"], "Bearer inventory-secret",
        )

    def test_dashboard_includes_discovered_unmanaged_local_services(self):
        values = {
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        }
        client = DockerBrokerClient({
            "updatedAt": 100,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "prowlarr12345",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": {"cpuPercent": 12.5, "onlineCpus": 4},
                },
                "sonarr": {
                    "id": "sonarr",
                    "containerId": "sonarr1234567",
                    "name": "umbrel-arr-sonarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": {
                        "cpuPercent": 25.0,
                        "onlineCpus": 4,
                        "memory": {"usedBytes": 100, "totalBytes": 1000, "percent": 10.0},
                    },
                },
            },
        })
        reconciler = Reconciler(Settings(values), client)
        self.assertTrue(reconciler.refresh_container_state())

        snapshot = reconciler.dashboard_snapshot()

        services = {item["id"]: item for item in snapshot["services"]}
        self.assertEqual(set(services), {"umbrelarr", "prowlarr", "sonarr"})
        self.assertTrue(services["prowlarr"]["managed"])
        self.assertFalse(services["sonarr"]["managed"])
        self.assertEqual(services["sonarr"]["detail"], "Installed locally and available to manage")
        self.assertEqual(services["sonarr"]["resources"]["cpu"]["percent"], 25.0)
        self.assertEqual(snapshot["inventory"]["discoveredCount"], 2)
        self.assertTrue(snapshot["inventory"]["available"])

    def test_docker_inventory_distinguishes_stopped_from_missing_apps(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })
        stopped_client = DockerBrokerClient({
            "updatedAt": 100,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "stopped12345",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "exited",
                    "health": "none",
                    "resources": None,
                },
            },
        })
        stopped = Reconciler(Settings(values), stopped_client).detect_apps()
        app = stopped["apps"][0]
        self.assertTrue(app["detected"])
        self.assertFalse(app["reachable"])
        self.assertEqual(app["action"], "start_service")
        self.assertEqual(stopped["detectedCount"], 1)
        self.assertFalse(stopped["canConfirm"])
        self.assertFalse(any(call[0] == "request" for call in stopped_client.calls))

        missing_client = DockerBrokerClient({"updatedAt": 101, "services": {}})
        missing = Reconciler(Settings(values), missing_client).detect_apps()
        app = missing["apps"][0]
        self.assertFalse(app["detected"])
        self.assertEqual(app["container"]["state"], "not_installed")
        self.assertEqual(app["action"], "install_or_start")
        self.assertEqual(missing["detectedCount"], 0)
        self.assertFalse(any(call[0] == "request" for call in missing_client.calls))

    def test_docker_inventory_retains_last_resource_sample_when_container_stops(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })
        client = DockerBrokerClient({
            "updatedAt": 1_700_000_000,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "running12345",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": {
                        "cpuPercent": 18.5,
                        "memory": {
                            "usedBytes": 512,
                            "totalBytes": 2048,
                            "percent": 25,
                        },
                        "blockIO": {"readBytes": 10, "writeBytes": 20},
                        "network": {"rxBytes": 30, "txBytes": 40},
                    },
                },
            },
        })
        reconciler = Reconciler(Settings(values), client)

        self.assertTrue(reconciler.refresh_container_state())
        first = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }["prowlarr"]
        self.assertEqual(first["resources"]["sampleState"], "current")
        self.assertEqual(first["resources"]["updatedAt"], 1_700_000_000)

        client.docker_snapshot = {
            "updatedAt": 1_700_000_015,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "running12345",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": None,
                },
            },
        }

        self.assertTrue(reconciler.refresh_container_state())
        unavailable = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }["prowlarr"]
        self.assertEqual(unavailable["container"]["state"], "running")
        self.assertEqual(unavailable["container"]["updatedAt"], 1_700_000_015)
        self.assertEqual(unavailable["resources"]["sampleState"], "last_sample")
        self.assertEqual(unavailable["resources"]["updatedAt"], 1_700_000_000)

        client.docker_snapshot = {
            "updatedAt": 1_700_000_030,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "running12345",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "exited",
                    "health": "none",
                    "resources": None,
                },
            },
        }

        self.assertTrue(reconciler.refresh_container_state())
        service = {
            item["id"]: item for item in reconciler.runtime.snapshot()["services"]
        }["prowlarr"]
        self.assertEqual(service["container"]["state"], "exited")
        self.assertEqual(service["container"]["updatedAt"], 1_700_000_030)
        self.assertEqual(service["resources"]["sampleState"], "last_sample")
        self.assertEqual(service["resources"]["updatedAt"], 1_700_000_000)
        self.assertEqual(service["resources"]["cpu"]["percent"], 18.5)
        self.assertEqual(service["resources"]["network"]["txBytes"], 40)

    def test_docker_inventory_keeps_missing_metrics_partial_not_zero(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })
        client = DockerBrokerClient({
            "updatedAt": 1_700_000_000,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "state": "running",
                    "health": "healthy",
                    "resources": {
                        "cpuPercent": None,
                        "onlineCpus": 4,
                        "cpuCapacityPercent": 400,
                        "memory": {
                            "usedBytes": 256,
                            "totalBytes": 2048,
                            "percent": 12.5,
                        },
                        "blockIO": None,
                        "network": None,
                    },
                },
            },
        })
        reconciler = Reconciler(Settings(values), client)

        self.assertTrue(reconciler.refresh_container_state())
        resources = next(
            item for item in reconciler.runtime.snapshot()["services"]
            if item["id"] == "prowlarr"
        )["resources"]
        self.assertEqual(resources["sampleState"], "current")
        self.assertNotIn("cpu", resources)
        self.assertNotIn("blockIo", resources)
        self.assertNotIn("network", resources)
        self.assertEqual(resources["memory"]["percent"], 12.5)

        client.docker_snapshot["updatedAt"] = 1_700_000_030
        client.docker_snapshot["services"]["prowlarr"]["resources"] = {
            "cpuPercent": None,
            "memory": None,
            "blockIO": None,
            "network": None,
        }
        self.assertTrue(reconciler.refresh_container_state())
        retained = next(
            item for item in reconciler.runtime.snapshot()["services"]
            if item["id"] == "prowlarr"
        )["resources"]
        self.assertEqual(retained["sampleState"], "last_sample")
        self.assertEqual(retained["updatedAt"], 1_700_000_000)
        self.assertNotIn("cpu", retained)

    def test_docker_inventory_failure_does_not_guess_from_http_reachability(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })
        client = DockerBrokerClient(error=RequestError("Docker broker offline"))
        snapshot = Reconciler(Settings(values), client).detect_apps()

        app = snapshot["apps"][0]
        self.assertFalse(app["detected"])
        self.assertEqual(app["action"], "docker_unavailable")
        self.assertIn("Docker inventory is unavailable", app["detail"])
        self.assertFalse(snapshot["docker"]["available"])
        self.assertFalse(any(call[0] == "request" for call in client.calls))

    def test_docker_inventory_refreshes_are_serialized(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })

        class BlockingBrokerClient(DockerBrokerClient):
            def __init__(self):
                super().__init__({"updatedAt": 100, "services": {}})
                self.entered = threading.Event()
                self.release = threading.Event()
                self.counter_lock = threading.Lock()
                self.active = 0
                self.max_active = 0
                self.broker_calls = 0

            def json(self, *args, **kwargs):
                if len(args) > 1 and str(args[1]).endswith("/v1/snapshot"):
                    with self.counter_lock:
                        self.broker_calls += 1
                        call_number = self.broker_calls
                        self.active += 1
                        self.max_active = max(self.max_active, self.active)
                    try:
                        if call_number == 1:
                            self.entered.set()
                            self.release.wait(timeout=1)
                        return super().json(*args, **kwargs)
                    finally:
                        with self.counter_lock:
                            self.active -= 1
                return super().json(*args, **kwargs)

        client = BlockingBrokerClient()
        reconciler = Reconciler(Settings(values), client)
        results = []
        first = threading.Thread(target=lambda: results.append(reconciler.refresh_container_state()))
        second = threading.Thread(target=lambda: results.append(reconciler.refresh_container_state()))
        first.start()
        self.assertTrue(client.entered.wait(timeout=1))
        second.start()
        client.release.set()
        first.join(timeout=1)
        second.join(timeout=1)

        self.assertEqual(results, [True, True])
        self.assertEqual(client.broker_calls, 2)
        self.assertEqual(client.max_active, 1)

    def test_failed_docker_refresh_makes_cached_inventory_non_authoritative(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })
        client = DockerBrokerClient({
            "updatedAt": 1_700_000_000,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "prowlarr1234",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": {
                        "cpuPercent": 7.25,
                        "memory": {
                            "usedBytes": 256,
                            "totalBytes": 2048,
                            "percent": 12.5,
                        },
                    },
                },
            },
        })
        reconciler = Reconciler(Settings(values), client)
        self.assertTrue(reconciler.detect_apps()["canConfirm"])

        client.docker_error = RequestError("Docker broker offline")
        self.assertFalse(reconciler.refresh_container_state())
        snapshot = reconciler.setup_snapshot()

        self.assertFalse(snapshot["docker"]["available"])
        app = snapshot["apps"][0]
        self.assertFalse(app["detected"])
        self.assertEqual(app["action"], "docker_unavailable")
        self.assertFalse(snapshot["canConfirm"])
        module = next(
            item for item in snapshot["modules"] if item["id"] == "prowlarr"
        )
        self.assertIsNone(module["installed"])
        self.assertEqual(module["container"], {})
        service = next(
            item for item in reconciler.runtime.snapshot()["services"]
            if item["id"] == "prowlarr"
        )
        self.assertEqual(service["container"]["state"], "unknown")
        self.assertEqual(service["resources"]["sampleState"], "last_sample")
        self.assertEqual(service["resources"]["updatedAt"], 1_700_000_000)

    def test_confirmation_revalidates_docker_state_after_review(self):
        values = environment(self.temp.name)
        values.update({
            "UMBREL_ARR_ENABLED_SERVICES": "prowlarr",
            "UMBREL_ARR_VPN_PROVIDER": "direct",
            "UMBREL_ARR_DOCKER_BROKER_URL": "http://docker-inventory:8765",
        })
        running = {
            "updatedAt": 1_700_000_000,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "prowlarr1234",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "running",
                    "health": "healthy",
                    "resources": None,
                },
            },
        }
        stopped = {
            "updatedAt": 1_700_000_001,
            "services": {
                "prowlarr": {
                    "id": "prowlarr",
                    "containerId": "prowlarr1234",
                    "name": "umbrel-arr-prowlarr_server_1",
                    "state": "exited",
                    "health": "none",
                    "resources": None,
                },
            },
        }
        scenarios = (
            ("stopped", stopped, None, "Install or start"),
            (
                "missing",
                {"updatedAt": 1_700_000_002, "services": {}},
                None,
                "Install or start",
            ),
            (
                "broker failure",
                running,
                RequestError("Docker broker offline"),
                "Docker inventory is unavailable",
            ),
        )

        for name, current, error, message in scenarios:
            with self.subTest(name=name):
                client = DockerBrokerClient(running)
                reconciler = Reconciler(Settings(values), client)
                self.assertTrue(reconciler.detect_apps()["canConfirm"])
                client.docker_snapshot = current
                client.docker_error = error

                with self.assertRaisesRegex(ValueError, message):
                    reconciler.confirm_setup("local")

                self.assertEqual(client.tags, [])
                self.assertFalse(any(
                    call[0] == "json"
                    and call[1] == "POST"
                    and call[2].endswith("/api/v1/tag")
                    for call in client.calls
                ))

    def test_module_catalog_derives_dependencies_from_selection(self):
        selected = {"umbrelarr", "prowlarr", "qbittorrent", "sonarr"}
        dependencies = dependencies_for(selected)
        self.assertEqual(dependencies["sonarr"], ("umbrelarr", "qbittorrent"))
        self.assertEqual(dependencies["prowlarr"], ("sonarr",))
        self.assertNotIn("privado-vpn", dependencies)
        self.assertEqual(validate_modules({"bazarr"}), ["Bazarr requires Sonarr and Radarr"])
        self.assertEqual(
            validate_modules({"jellyfin"}),
            ["Jellyfin requires at least one Sonarr, Radarr, or Lidarr module"],
        )
        media_dependencies = dependencies_for({"prowlarr", "sonarr", "jellyfin"})
        self.assertEqual(media_dependencies["jellyfin"], ("umbrelarr", "sonarr"))
        self.assertTrue(CORE_MODULES <= set(selected))

    def test_selected_modules_limit_read_only_detection(self):
        active_modules = self.reconciler.enabled_modules
        snapshot = self.reconciler.select_and_detect(
            ["prowlarr", "sonarr", "qbittorrent"], "direct",
        )
        self.assertEqual(snapshot["vpnProvider"], "direct")
        self.assertNotIn("profiles", snapshot)
        self.assertEqual(snapshot["requiredCount"], 3)
        self.assertEqual(
            {item["id"] for item in snapshot["apps"]},
            {"prowlarr", "sonarr", "qbittorrent"},
        )
        self.assertIn("privado-vpn", self.reconciler.enabled_modules)
        self.assertEqual(self.reconciler.enabled_modules, active_modules)
        self.assertNotIn("privado-vpn", snapshot["enabledServices"])
        self.assertTrue(snapshot["configurationChanged"])
        requests = [call for call in self.client.calls if call[0] == "request"]
        self.assertEqual(len(requests), 3)
        self.assertTrue(all(call[1] == "GET" for call in requests))

    def test_media_server_detection_uses_public_read_only_probes(self):
        snapshot = self.reconciler.select_and_detect(
            ["prowlarr", "sonarr", "jellyfin", "plex"], "direct",
        )
        self.assertTrue(snapshot["canConfirm"])
        requested = {call[2] for call in self.client.calls if call[0] == "request"}
        self.assertIn("http://jellyfin:8096/System/Info/Public", requested)
        self.assertIn("http://plex:32400/identity", requested)

    def test_jellyfin_reconciliation_creates_only_named_owned_libraries(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_ENABLED_SERVICES"] = "prowlarr,sonarr,radarr,jellyfin"
        client = MediaServerClient()
        reconciler = Reconciler(Settings(values), client)

        first = reconciler.configure_jellyfin()
        second = reconciler.configure_jellyfin()

        self.assertIn("2 managed libraries", first)
        self.assertIn("0 created, 0 paths added", second)
        self.assertEqual(
            {item["Name"] for item in client.jellyfin_folders},
            {"Personal Movies", "Umbrel Arr TV", "Umbrel Arr Movies"},
        )
        mutations = [
            call for call in client.calls
            if call[0] == "json" and call[1] == "POST" and "/Library/VirtualFolders" in call[2]
        ]
        self.assertEqual(len(mutations), 4)
        self.assertTrue(all(call[5] == {"X-Emby-Token": "jellyfin-key"} for call in mutations))

    def test_jellyfin_bootstrap_reuses_one_named_key_without_exposing_secrets(self):
        client = JellyfinBootstrapClient(keys=[{
            "Name": "umbrelarr",
            "AccessToken": "existing-dedicated-private-key",
        }])
        reconciler, before, jellyfin = self.jellyfin_bootstrap_reconciler(client)
        self.assertEqual(jellyfin["action"], "create_api_key")
        module = next(item for item in before["modules"] if item["id"] == "jellyfin")
        self.assertEqual(module["credentialSetup"], "jellyfin_admin")

        snapshot = reconciler.bootstrap_credential(
            "jellyfin", "admin", "private-password",
        )

        self.assertEqual(client.created, 0)
        self.assertEqual(client.logged_out, 1)
        self.assertEqual(
            reconciler.settings.key("jellyfin"),
            "existing-dedicated-private-key",
        )
        module = next(item for item in snapshot["modules"] if item["id"] == "jellyfin")
        self.assertEqual(module["credentialSource"], "service_api")
        self.assertTrue(module["credentialConfigured"])
        self.assertNotIn("private-password", str(snapshot))
        self.assertNotIn("private-admin-session", str(snapshot))
        self.assertNotIn("existing-dedicated-private-key", str(snapshot))
        self.assertIn(
            "Jellyfin API key connected through its administrator API",
            str(reconciler.runtime.snapshot()["events"]),
        )

    def test_jellyfin_bootstrap_creates_and_validates_a_missing_named_key(self):
        client = JellyfinBootstrapClient()
        reconciler, _before, jellyfin = self.jellyfin_bootstrap_reconciler(client)
        self.assertEqual(jellyfin["action"], "create_api_key")
        self.assertFalse(any(
            call[0] == "json" and call[1] == "POST" and "/Auth/Keys" in call[2]
            for call in client.calls
        ), "ordinary detection must not create service credentials")

        snapshot = reconciler.bootstrap_credential(
            "jellyfin", "admin", "private-password",
        )

        self.assertEqual(client.created, 1)
        self.assertEqual(client.logged_out, 1)
        self.assertEqual(reconciler.settings.key("jellyfin"), "dedicated-key-1")
        detected = next(item for item in snapshot["apps"] if item["id"] == "jellyfin")
        self.assertTrue(detected["credentials"])
        self.assertEqual(detected["action"], "none")
        self.assertIn("created and verified", detected["detail"])
        create_calls = [
            call for call in client.calls
            if call[1] == "POST" and "/Auth/Keys?app=umbrelarr" in call[2]
        ]
        self.assertEqual(len(create_calls), 1)

    def test_jellyfin_bootstrap_rejects_invalid_or_non_admin_login_safely(self):
        invalid = JellyfinBootstrapClient(reject_login=True)
        reconciler, _snapshot, _jellyfin = self.jellyfin_bootstrap_reconciler(invalid)
        with self.assertRaisesRegex(ValueError, "rejected the administrator") as context:
            reconciler.bootstrap_credential(
                "jellyfin", "admin", "private-password",
            )
        self.assertNotIn("private-password", str(context.exception))
        self.assertNotIn("private-admin-session", str(context.exception))
        self.assertEqual(reconciler.settings.key("jellyfin"), "")

        non_admin = JellyfinBootstrapClient(administrator=False)
        reconciler, _snapshot, _jellyfin = self.jellyfin_bootstrap_reconciler(non_admin)
        with self.assertRaisesRegex(ValueError, "administrator account"):
            reconciler.bootstrap_credential(
                "jellyfin", "viewer", "private-password",
            )
        self.assertEqual(non_admin.created, 0)
        self.assertEqual(non_admin.logged_out, 1)
        self.assertEqual(reconciler.settings.key("jellyfin"), "")

    def test_jellyfin_bootstrap_rejects_duplicates_and_network_failure_without_leaks(self):
        duplicate = JellyfinBootstrapClient(keys=[
            {"Name": "umbrelarr", "AccessToken": "private-key-one"},
            {"AppName": "Umbrelarr", "AccessToken": "private-key-two"},
        ])
        reconciler, _snapshot, _jellyfin = self.jellyfin_bootstrap_reconciler(duplicate)
        with self.assertRaisesRegex(ValueError, "multiple API keys") as context:
            reconciler.bootstrap_credential(
                "jellyfin", "admin", "private-password",
            )
        self.assertNotIn("private-key", str(context.exception))
        self.assertEqual(duplicate.logged_out, 1)

        unavailable = JellyfinBootstrapClient(fail_key_list=True, fail_logout=True)
        reconciler, _snapshot, _jellyfin = self.jellyfin_bootstrap_reconciler(unavailable)
        with self.assertRaisesRegex(RuntimeError, "could not list its API keys") as context:
            reconciler.bootstrap_credential(
                "jellyfin", "admin", "private-password",
            )
        self.assertNotIn("private-admin-session", str(context.exception))
        self.assertEqual(unavailable.logged_out, 1)
        self.assertEqual(reconciler.settings.key("jellyfin"), "")

    def test_jellyfin_bootstrap_rejects_a_configured_invalid_environment_key(self):
        client = JellyfinBootstrapClient()
        reconciler, snapshot, jellyfin = self.jellyfin_bootstrap_reconciler(
            client, "stale-environment-private-key",
        )
        self.assertEqual(jellyfin["action"], "invalid_credentials")
        module = next(item for item in snapshot["modules"] if item["id"] == "jellyfin")
        self.assertTrue(module["environmentCredentialConfigured"])

        with self.assertRaisesRegex(ValueError, "UMBREL_ARR_JELLYFIN_API_KEY") as context:
            reconciler.bootstrap_credential(
                "jellyfin", "admin", "private-password",
            )

        self.assertNotIn("stale-environment-private-key", str(context.exception))
        self.assertFalse(any("/Users/AuthenticateByName" in call[2] for call in client.calls))

    def test_plex_reconciliation_creates_only_named_owned_libraries(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_ENABLED_SERVICES"] = "prowlarr,sonarr,radarr,plex"
        client = MediaServerClient()
        reconciler = Reconciler(Settings(values), client)

        first = reconciler.configure_plex()
        second = reconciler.configure_plex()

        self.assertIn("2 managed libraries", first)
        self.assertIn("0 created", second)
        self.assertEqual(
            {item["title"] for item in client.plex_sections},
            {"Personal Movies", "Umbrel Arr TV", "Umbrel Arr Movies"},
        )
        creates = [
            call for call in client.calls
            if call[0] == "json" and call[1] == "POST" and "/library/sections?" in call[2]
        ]
        self.assertEqual(len(creates), 2)
        self.assertTrue(all(call[5] == {"X-Plex-Token": "plex-key"} for call in creates))

    def test_plex_does_not_overwrite_a_named_library_with_a_different_path(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_ENABLED_SERVICES"] = "prowlarr,radarr,plex"
        client = MediaServerClient()
        client.plex_sections.append({
            "key": "91", "title": "Umbrel Arr Movies", "Location": [{"path": "/elsewhere"}],
        })
        reconciler = Reconciler(Settings(values), client)

        status, detail = reconciler.configure_plex()

        self.assertEqual(status, "action_required")
        self.assertIn("Umbrel Arr Movies", detail)
        self.assertFalse(any(call[1] in {"PUT", "DELETE"} for call in client.calls))

    def test_modular_selection_and_provider_restore_from_api_markers(self):
        client = FakeClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.select_and_detect(["prowlarr", "sonarr"], "direct")
        reconciler.reconcile_async = lambda: True
        snapshot = reconciler.confirm_setup(
            "local", enabled_services=["prowlarr", "sonarr"], vpn_provider="direct",
        )
        self.assertTrue(snapshot["confirmed"])
        labels = {item["label"] for item in client.tags}
        self.assertIn(MODULE_CATALOG_MARKER_TAG, labels)
        self.assertIn(f"{VPN_PROVIDER_MARKER_PREFIX}direct", labels)
        self.assertIn(f"{MODULE_MARKER_PREFIX}sonarr", labels)
        self.assertNotIn(f"{MODULE_MARKER_PREFIX}privado-vpn", labels)

        restored = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(restored.ensure_setup())
        self.assertEqual(restored.vpn_provider.id, "direct")
        self.assertEqual(restored.enabled_modules, {"umbrelarr", "prowlarr", "sonarr"})
        self.assertEqual([arr.slug for arr in restored.arrs], ["sonarr"])

    def test_legacy_setup_without_module_markers_keeps_complete_privado_stack(self):
        client = FakeClient()
        client.tags.append({"id": 1, "label": SETUP_MARKER_TAG})
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(reconciler.ensure_setup())
        self.assertEqual(reconciler.vpn_provider.id, "privado")
        self.assertEqual(set(reconciler._selected_apps()), set(REQUIRED_APPS))

    def test_confirmed_stack_can_detect_and_apply_a_new_module_selection(self):
        client = FakeClient()
        labels = [
            SETUP_MARKER_TAG,
            SETUP_READY_MARKER_TAG,
            MODULE_CATALOG_MARKER_TAG,
            f"{VPN_PROVIDER_MARKER_PREFIX}privado",
            f"{MODULE_MARKER_PREFIX}umbrelarr",
            f"{MODULE_MARKER_PREFIX}prowlarr",
            f"{MODULE_MARKER_PREFIX}privado-vpn",
            f"{MODULE_MARKER_PREFIX}sonarr",
        ]
        client.tags.extend({"id": index + 1, "label": label} for index, label in enumerate(labels))
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(reconciler.ensure_setup_ready())
        active_modules = set(reconciler.enabled_modules)
        active_services = {
            item["id"] for item in reconciler.runtime.snapshot()["services"]
        }

        snapshot = reconciler.select_and_detect(["prowlarr", "sonarr"], "direct")

        self.assertTrue(snapshot["configurationChanged"])
        self.assertEqual(snapshot["phase"], "ready")
        self.assertTrue(snapshot["canConfirm"])
        self.assertEqual(snapshot["vpnProvider"], "direct")
        self.assertEqual(set(snapshot["activeEnabledServices"]), active_modules)
        modules = {item["id"]: item for item in snapshot["modules"]}
        self.assertTrue(modules["sonarr"]["active"])
        self.assertTrue(modules["sonarr"]["enabled"])
        self.assertTrue(modules["privado-vpn"]["active"])
        self.assertFalse(modules["privado-vpn"]["enabled"])
        self.assertEqual(reconciler.enabled_modules, active_modules)
        self.assertEqual(reconciler.vpn_provider.id, "privado")
        self.assertEqual(
            {item["id"] for item in reconciler.runtime.snapshot()["services"]},
            active_services,
        )

        cancelled = reconciler.cancel_selection_change()
        self.assertEqual(cancelled["phase"], "confirmed")
        self.assertFalse(cancelled["configurationChanged"])
        self.assertEqual(reconciler.enabled_modules, active_modules)

        reconciler.select_and_detect(["prowlarr", "sonarr"], "direct")
        reconciler.reconcile_async = lambda: True
        applied = reconciler.confirm_setup(
            "local", enabled_services=["prowlarr", "sonarr"], vpn_provider="direct",
        )
        self.assertEqual(applied["phase"], "confirmed")
        self.assertEqual(reconciler.enabled_modules, {"umbrelarr", "prowlarr", "sonarr"})
        self.assertEqual(reconciler.vpn_provider.id, "direct")
        marker_labels = {item["label"] for item in client.tags}
        self.assertIn(f"{MODULE_MARKER_PREFIX}sonarr", marker_labels)
        self.assertNotIn(f"{MODULE_MARKER_PREFIX}privado-vpn", marker_labels)

    def test_optional_service_can_be_removed_without_touching_the_installed_app(self):
        reconciler, client = self.confirmed_reconciler(
            ["umbrelarr", "prowlarr", "qbittorrent"],
        )

        snapshot = reconciler.remove_service("qbittorrent")

        self.assertEqual(reconciler.enabled_modules, CORE_MODULES)
        self.assertEqual(set(snapshot["activeEnabledServices"]), CORE_MODULES)
        self.assertNotIn(
            f"{MODULE_MARKER_PREFIX}qbittorrent",
            {item["label"] for item in client.tags},
        )
        app_mutations = [
            call for call in client.calls
            if call[0] == "json"
            and call[1] in {"POST", "PUT", "DELETE"}
            and "/api/v1/tag" not in call[2]
        ]
        self.assertEqual(app_mutations, [])
        self.assertTrue(any(
            "Stopped managing qBittorrent" in event["message"]
            for event in reconciler.runtime.snapshot()["events"]
        ))

    def test_removing_privado_switches_the_managed_provider_to_direct(self):
        reconciler, client = self.confirmed_reconciler(
            ["umbrelarr", "prowlarr", "privado-vpn"], "privado",
        )

        snapshot = reconciler.remove_service("privado-vpn")

        self.assertEqual(reconciler.vpn_provider.id, "direct")
        self.assertEqual(set(snapshot["activeEnabledServices"]), CORE_MODULES)
        labels = {item["label"] for item in client.tags}
        self.assertIn(f"{VPN_PROVIDER_MARKER_PREFIX}direct", labels)
        self.assertNotIn(f"{VPN_PROVIDER_MARKER_PREFIX}privado", labels)
        self.assertNotIn(f"{MODULE_MARKER_PREFIX}privado-vpn", labels)

    def test_removal_rejects_required_services_and_dependency_breakage(self):
        reconciler, client = self.confirmed_reconciler([
            "umbrelarr", "prowlarr", "sonarr", "radarr", "bazarr",
        ])
        labels = {item["label"] for item in client.tags}

        with self.assertRaisesRegex(ValueError, "required by umbrelarr"):
            reconciler.remove_service("prowlarr")
        with self.assertRaisesRegex(ValueError, "Remove the dependent service first"):
            reconciler.remove_service("sonarr")

        self.assertIn("sonarr", reconciler.enabled_modules)
        self.assertEqual({item["label"] for item in client.tags}, labels)

    def test_failed_marker_write_keeps_the_service_in_the_active_fleet(self):
        reconciler, client = self.confirmed_reconciler(
            ["umbrelarr", "prowlarr", "qbittorrent"],
            client=FailingTagDeleteClient(),
        )
        active_runtime = reconciler.runtime

        with self.assertRaisesRegex(RuntimeError, "marker update failed"):
            reconciler.remove_service("qbittorrent")

        self.assertIn("qbittorrent", reconciler.enabled_modules)
        self.assertIs(reconciler.runtime, active_runtime)
        self.assertIn(
            f"{MODULE_MARKER_PREFIX}qbittorrent",
            {item["label"] for item in client.tags},
        )

    def test_failed_later_addition_keeps_the_active_fleet_and_markers(self):
        client = QbitAuthClient(active_password="different-password")
        labels = [
            SETUP_MARKER_TAG,
            SETUP_READY_MARKER_TAG,
            MODULE_CATALOG_MARKER_TAG,
            f"{VPN_PROVIDER_MARKER_PREFIX}direct",
            f"{MODULE_MARKER_PREFIX}umbrelarr",
            f"{MODULE_MARKER_PREFIX}prowlarr",
            f"{MODULE_MARKER_PREFIX}sonarr",
        ]
        client.tags.extend(
            {"id": index + 1, "label": label}
            for index, label in enumerate(labels)
        )
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(reconciler.ensure_setup_ready())
        active_modules = reconciler.enabled_modules
        active_runtime = reconciler.runtime

        reviewed = reconciler.select_and_detect(
            ["prowlarr", "sonarr", "qbittorrent"], "direct",
        )
        self.assertTrue(reviewed["canConfirm"])
        with self.assertRaisesRegex(ValueError, "one-time admin password"):
            reconciler.confirm_setup(
                "local",
                qbittorrent_temporary_password="wrong-password",
                enabled_services=["prowlarr", "sonarr", "qbittorrent"],
                vpn_provider="direct",
            )

        self.assertEqual(reconciler.enabled_modules, active_modules)
        self.assertIs(reconciler.runtime, active_runtime)
        self.assertNotIn(
            f"{MODULE_MARKER_PREFIX}qbittorrent",
            {item["label"] for item in client.tags},
        )
        retry = reconciler.setup_snapshot()
        self.assertTrue(retry["configurationChanged"])
        self.assertEqual(retry["phase"], "ready")

    def test_reconciliation_is_blocked_until_explicit_setup(self):
        snapshot = self.reconciler.setup_snapshot()
        self.assertFalse(snapshot["confirmed"])
        services = {item["id"]: item for item in self.reconciler.runtime.snapshot()["services"]}
        self.assertEqual(services["umbrelarr"]["status"], "action_required")
        with self.assertRaisesRegex(RuntimeError, "Complete app discovery"):
            self.reconciler.reconcile_async()

    def test_detection_is_read_only_and_finds_installed_apps(self):
        snapshot = self.reconciler.detect_apps()
        self.assertTrue(snapshot["canConfirm"])
        self.assertEqual(snapshot["phase"], "ready")
        self.assertFalse(snapshot["confirmed"])
        self.assertTrue(snapshot["canConfirm"])
        self.assertEqual(snapshot["detectedCount"], len(REQUIRED_APPS))
        requests = [call for call in self.client.calls if call[0] == "request"]
        self.assertGreaterEqual(len(requests), len(REQUIRED_APPS))
        self.assertTrue(all(call[1] == "GET" for call in requests))
        self.assertFalse(any(call[1] in {"POST", "PUT", "DELETE"} for call in self.client.calls))
        self.assertTrue(all({"reachable", "credentials", "action"} <= item.keys() for item in snapshot["apps"]))

    def test_detection_rejects_a_stale_api_key_before_apply(self):
        original = self.client.json

        def json_call(method, url, api_key=None, payload=None, headers=None):
            if url.endswith("/api/v3/system/status"):
                raise RequestError("Unauthorized", 401)
            return original(method, url, api_key, payload, headers)

        self.client.json = json_call
        snapshot = self.reconciler.select_and_detect(
            ["prowlarr", "sonarr"], "direct",
        )

        self.assertFalse(snapshot["canConfirm"])
        sonarr = next(item for item in snapshot["apps"] if item["id"] == "sonarr")
        self.assertTrue(sonarr["reachable"])
        self.assertFalse(sonarr["credentials"])
        self.assertEqual(sonarr["action"], "invalid_credentials")
        self.assertIn("rejected", sonarr["detail"])
        with self.assertRaisesRegex(ValueError, "Resolve these service connections"):
            self.reconciler.confirm_setup(
                "local", enabled_services=["prowlarr", "sonarr"],
                vpn_provider="direct",
            )

    def test_confirmation_detects_storage_when_no_choice_is_submitted(self):
        self.reconciler.detect_apps()
        self.reconciler.reconcile_async = lambda: True

        snapshot = self.reconciler.confirm_setup()

        self.assertTrue(snapshot["confirmed"])
        self.assertEqual(self.reconciler.storage.snapshot()["mode"], "local")
        self.assertTrue(any(item.get("label") == SETUP_MARKER_TAG for item in self.client.tags))

    def test_confirmation_rejects_missing_generated_api_key(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_SONARR_API_KEY"] = ""
        reconciler = Reconciler(Settings(values), self.client)
        snapshot = reconciler.detect_apps()
        self.assertFalse(snapshot["canConfirm"])
        sonarr = next(item for item in snapshot["apps"] if item["id"] == "sonarr")
        self.assertIn("generated API key", sonarr["detail"])
        with self.assertRaisesRegex(ValueError, "Sonarr"):
            reconciler.confirm_setup("local")

    def test_confirmation_reports_missing_temporary_qbittorrent_password_after_deterministic_attempt(self):
        client = QbitAuthClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        snapshot = reconciler.detect_apps()
        qbit = next(item for item in snapshot["apps"] if item["id"] == "qbittorrent")
        self.assertEqual(qbit["action"], "temporary_password_required")
        with self.assertRaisesRegex(ValueError, "one-time admin password"):
            reconciler.confirm_setup("local")
        self.assertTrue(any(item.get("label") == SETUP_MARKER_TAG for item in client.tags))

    def test_fresh_qbittorrent_uses_temporary_password_and_secure_api_preferences(self):
        client = QbitAuthClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler._onboard_qbittorrent("admin", "temporary-password")
        self.assertEqual(client.active_password, "umbrel-password")
        self.assertTrue(client.preferences["web_ui_csrf_protection_enabled"])
        self.assertTrue(client.preferences["web_ui_clickjacking_protection_enabled"])
        self.assertTrue(client.preferences["web_ui_host_header_validation_enabled"])
        self.assertFalse(client.preferences["web_ui_secure_cookie_enabled"])
        self.assertFalse(client.preferences["web_ui_upnp"])
        self.assertFalse(client.preferences["bypass_local_auth"])
        self.assertFalse(client.preferences["bypass_auth_subnet_whitelist_enabled"])
        self.assertEqual(client.preferences["bypass_auth_subnet_whitelist"], "")
        self.assertIn("qbit", client.preferences["web_ui_domain_list"])
        preference_call = next(call for call in client.calls if call[0] == "form" and call[2].endswith("setPreferences"))
        self.assertEqual(preference_call[3]["Cookie"], "SID=test-session")

    def test_qbittorrent_401_falls_back_to_the_one_time_password(self):
        client = QbitAuthClient(
            active_password="correct-temporary", rejected_login_status=401,
        )
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler._onboard_qbittorrent("admin", "correct-temporary")
        passwords = [
            call[4]["password"] for call in client.calls
            if call[0] == "form" and call[2].endswith("auth/login")
        ]
        self.assertEqual(passwords[:2], ["umbrel-password", "correct-temporary"])
        self.assertEqual(client.active_password, "umbrel-password")

    def test_legacy_manager_password_is_rotated_to_qbittorrent_password(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_QBITTORRENT_LEGACY_PASSWORD"] = "legacy-manager-password"
        client = QbitAuthClient(active_password="legacy-manager-password")
        reconciler = Reconciler(Settings(values), client)

        reconciler._onboard_qbittorrent("admin", "")

        passwords = [
            call[4]["password"] for call in client.calls
            if call[0] == "form" and call[2].endswith("auth/login")
        ]
        self.assertEqual(passwords[:2], ["umbrel-password", "legacy-manager-password"])
        self.assertEqual(client.active_password, "umbrel-password")

    def test_current_qbittorrent_versioned_session_cookie_is_accepted(self):
        client = QbitAuthClient(session_cookie_name="QBT_SID_8080")
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler._onboard_qbittorrent("admin", "temporary-password")
        self.assertEqual(reconciler._qbittorrent_cookie, "QBT_SID_8080=test-session")
        preference_call = next(
            call for call in client.calls
            if call[0] == "form" and call[2].endswith("setPreferences")
        )
        self.assertEqual(preference_call[3]["Cookie"], "QBT_SID_8080=test-session")

    def test_legacy_unauthenticated_qbittorrent_is_secured_then_reauthenticated(self):
        client = QbitAuthClient(allow_unauthenticated=True)
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler._onboard_qbittorrent("admin", "")
        self.assertEqual(client.active_password, "umbrel-password")
        self.assertEqual(reconciler._qbittorrent_cookie, "SID=test-session")

    def test_already_configured_qbittorrent_uses_deterministic_password(self):
        client = QbitAuthClient(active_password="umbrel-password")
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler._onboard_qbittorrent("admin", "")
        login = next(call for call in client.calls if call[0] == "form" and call[2].endswith("auth/login"))
        self.assertEqual(login[4]["password"], "umbrel-password")
        self.assertEqual(login[3]["Origin"], "http://qbit:8080")

    def test_consent_marker_survives_failed_qbittorrent_onboarding(self):
        client = QbitAuthClient(active_password="different")
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.detect_apps()
        with self.assertRaisesRegex(ValueError, "one-time admin password"):
            reconciler.confirm_setup("local", qbittorrent_temporary_password="wrong")
        self.assertTrue(any(item.get("label") == SETUP_MARKER_TAG for item in client.tags))
        client.calls.clear()
        reconciler.reconcile()
        with self.assertRaisesRegex(RuntimeError, "Complete app discovery"):
            reconciler.reconcile_async()
        self.assertFalse(any(call[1] in {"POST", "PUT", "DELETE"} for call in client.calls))
        retry = reconciler.setup_snapshot()
        self.assertTrue(retry["confirmed"])
        self.assertEqual(retry["phase"], "action_required")
        client.active_password = "correct-temporary"
        reconciler.reconcile_async = lambda: True
        completed = reconciler.confirm_setup(
            "local", qbittorrent_temporary_password="correct-temporary",
        )
        self.assertEqual(completed["phase"], "confirmed")
        self.assertTrue(any(item.get("label") == SETUP_READY_MARKER_TAG for item in client.tags))
        restored = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(restored.ensure_setup())
        self.assertEqual(restored.setup_snapshot()["phase"], "confirmed")

    def test_invalid_adopted_storage_is_rejected_before_consent_or_mutation(self):
        client = QbitAuthClient(allow_unauthenticated=True)
        for slug, path in LOCAL_ROOTS.items():
            client.roots[Settings(environment()).url(slug)] = [{"id": 1, "path": path}]
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.detect_apps()
        client.calls.clear()
        with self.assertRaisesRegex(ValueError, "root-folder ID"):
            reconciler.confirm_setup("adopt", {"sonarr": 1})
        self.assertFalse(any(item.get("label") == SETUP_MARKER_TAG for item in client.tags))
        self.assertFalse(any(call[1] in {"POST", "PUT", "DELETE"} for call in client.calls))

    def test_adopted_root_ids_restore_from_prowlarr_api_markers(self):
        client = FakeClient()
        for index, (slug, local_path) in enumerate(LOCAL_ROOTS.items()):
            host = Settings(environment()).url(slug)
            client.roots[host] = [
                {"id": 1, "path": local_path},
                {"id": 2, "path": NETWORK_ROOTS[slug]},
            ]
        reconciler = Reconciler(Settings(environment()), client)
        reconciler._setup_complete = True
        reconciler._setup_ready = True
        reconciler.reconcile_async = lambda: True
        selected = reconciler.save_storage("adopt", {slug: 2 for slug in LOCAL_ROOTS})
        self.assertEqual(selected["roots"], NETWORK_ROOTS)
        restored = Reconciler(Settings(environment()), client)
        snapshot = restored.storage_snapshot()
        self.assertEqual(snapshot["mode"], "adopted")
        self.assertEqual(snapshot["rootIds"], {slug: 2 for slug in LOCAL_ROOTS})
        self.assertFalse(snapshot["actionRequired"])

    def test_ready_marker_without_consent_cannot_authorize_mutations(self):
        client = FakeClient()
        client.tags.append({"id": 1, "label": SETUP_READY_MARKER_TAG})
        reconciler = Reconciler(Settings(environment()), client)
        self.assertFalse(reconciler.ensure_setup_ready())
        snapshot = reconciler.setup_snapshot()
        self.assertFalse(snapshot["confirmed"])
        self.assertNotEqual(snapshot["phase"], "confirmed")
        with self.assertRaises(RuntimeError):
            reconciler.reconcile_async()

    def test_confirmation_persists_setup_as_a_prowlarr_api_marker(self):
        client = StackClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.detect_apps()
        reconciler.reconcile_async = lambda: True

        snapshot = reconciler.confirm_setup("local")

        self.assertTrue(snapshot["confirmed"])
        self.assertIn({"label": SETUP_MARKER_TAG, "id": 1}, client.tags)
        self.assertTrue(any(item.get("label") == SETUP_READY_MARKER_TAG for item in client.tags))
        restored = Reconciler(Settings(environment(self.temp.name)), client)
        self.assertTrue(restored.ensure_setup())
        self.assertEqual(restored.setup_snapshot()["phase"], "confirmed")

    def test_detection_reports_an_unreachable_required_app(self):
        original = self.client.request

        def request(method, url, headers=None, body=None, timeout=20):
            if url.startswith("http://lidarr:"):
                raise RequestError("unreachable")
            return original(method, url, headers, body, timeout)

        self.client.request = request
        snapshot = self.reconciler.detect_apps()
        self.assertFalse(snapshot["canConfirm"])
        lidarr = next(item for item in snapshot["apps"] if item["id"] == "lidarr")
        self.assertFalse(lidarr["detected"])

    def test_environment_api_key_overrides_discovery(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_MANAGED_CONFIG_DIR"] = str(Path(self.temp.name) / "managed")
        self.assertEqual(Settings(values).key("sonarr"), "sonarr-key")

    def test_vpn_requires_login_then_reports_health(self):
        self.assertEqual(self.reconciler.check_vpn()[0], "action_required")
        self.client.vpn = {"credentialsConfigured": True, "state": "healthy", "publicIp": "203.0.113.7"}
        self.assertIn("203.0.113.7", self.reconciler.check_vpn())

    def test_vpn_reports_selected_server_when_exit_ip_is_unknown(self):
        self.client.vpn = {
            "credentialsConfigured": True,
            "state": "healthy",
            "publicIp": "unknown",
            "server": "nl.example.vpn",
        }

        self.assertEqual(
            self.reconciler.check_vpn(),
            "WireGuard and SOCKS5 are healthy via nl.example.vpn",
        )

    def test_generic_socks_provider_probes_the_selected_endpoint(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_SOCKS5_HOST"] = "socks-gateway"
        values["UMBREL_ARR_SOCKS5_PORT"] = "1088"
        reconciler = Reconciler(Settings(values), self.client)
        reconciler._set_modules({"prowlarr"}, "generic-socks5")

        self.assertIn("socks-gateway:1088", reconciler.check_vpn())
        self.assertIn(("tcp", "socks-gateway", 1088, 3), self.client.calls)

    def test_generic_socks_setup_is_blocked_until_the_endpoint_is_configured(self):
        snapshot = self.reconciler.select_and_detect(["prowlarr"], "generic-socks5")

        self.assertFalse(snapshot["canConfirm"])
        self.assertEqual(snapshot["vpnStatus"]["status"], "action_required")
        self.assertIn("UMBREL_ARR_SOCKS5_HOST", snapshot["vpnStatus"]["detail"])

    def test_unreachable_external_vpn_becomes_waiting_without_aborting_reconciliation(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_SOCKS5_HOST"] = "missing-gateway"
        reconciler = Reconciler(Settings(values), self.client)
        reconciler._set_modules({"prowlarr"}, "generic-socks5")
        reconciler._setup_complete = True
        reconciler._setup_ready = True
        self.client.tcp = lambda *_args, **_kwargs: (_ for _ in ()).throw(RequestError("offline"))

        reconciler.reconcile()

        services = {item["id"]: item for item in reconciler.runtime.snapshot()["services"]}
        self.assertEqual(services["umbrelarr"]["status"], "waiting")
        self.assertEqual(services["prowlarr"]["status"], "waiting")
        self.assertFalse(reconciler.runtime.running)

    def test_vpn_login_is_forwarded_without_persistence(self):
        self.reconciler.reconcile_async = lambda: True
        self.reconciler.save_vpn_login("member", "very-secret")
        call = self.client.calls[-1]
        self.assertEqual(call[2], "http://vpn:8080/setup")
        self.assertEqual(call[4]["username"], "member")
        self.assertEqual(call[4]["password"], "very-secret")
        self.assertFalse(any("very-secret" in path.read_text() for path in Path(self.temp.name).glob("**/*") if path.is_file()))

    def test_library_save_applies_roots_then_starts_api_reconciliation(self):
        started = []
        self.reconciler.reconcile_async = lambda: started.append(True) or True
        self.reconciler._setup_complete = True
        self.reconciler._setup_ready = True
        snapshot = self.reconciler.save_storage("network", {})
        self.assertEqual(snapshot["mode"], "network")
        self.assertEqual(self.reconciler.arrs[0].root, "/network/shows")
        self.assertEqual(started, [True])
        event = self.reconciler.runtime.snapshot()["events"][0]["message"]
        self.assertIn("applied through service APIs", event)

    def test_individual_library_save_preserves_every_other_root(self):
        self.reconciler.reconcile_async = lambda: True
        self.reconciler._setup_complete = True
        self.reconciler._setup_ready = True
        self.reconciler.save_storage("local", {})

        snapshot = self.reconciler.save_library_storage("sonarr", "network")

        self.assertEqual(snapshot["mode"], "adopted")
        self.assertEqual(snapshot["roots"]["sonarr"], NETWORK_ROOTS["sonarr"])
        for slug, path in LOCAL_ROOTS.items():
            if slug != "sonarr":
                self.assertEqual(snapshot["roots"][slug], path)
        library = next(item for item in snapshot["libraries"] if item["key"] == "sonarr")
        self.assertEqual(library["source"], "network")
        self.assertEqual(library["rootId"], 2)
        self.assertEqual(len(library["candidates"]), 2)
        self.assertIn("Sonarr library root updated", self.reconciler.runtime.snapshot()["events"][0]["message"])

    def test_individual_library_can_adopt_only_a_reported_existing_root(self):
        self.reconciler.reconcile_async = lambda: True
        self.reconciler._setup_complete = True
        self.reconciler._setup_ready = True
        self.reconciler.save_storage("local", {})
        radarr_url = self.reconciler.settings.url("radarr")
        self.client.roots[radarr_url].append({"id": 2, "path": "/media/movies"})

        snapshot = self.reconciler.save_library_storage("radarr", "existing", 2)

        library = next(item for item in snapshot["libraries"] if item["key"] == "radarr")
        self.assertEqual(library["source"], "existing")
        self.assertEqual(library["root"], "/media/movies")
        self.assertEqual(snapshot["roots"]["sonarr"], LOCAL_ROOTS["sonarr"])
        with self.assertRaisesRegex(ValueError, "not available"):
            self.reconciler.save_library_storage("radarr", "existing", 999)

    def test_library_filesystem_browser_normalizes_folders_and_checks_all_arrs(self):
        sonarr_url = self.reconciler.settings.url("sonarr")
        self.client.filesystems[sonarr_url] = {
            "/media": {
                "parent": "/",
                "directories": [
                    {"name": "Zeta", "path": "/media/Zeta/"},
                    {"Name": "alpha", "Path": "/media/alpha"},
                    {"name": "Relative", "path": "relative"},
                ],
            },
        }

        snapshot = self.reconciler.browse_library_filesystem("sonarr", "/media")

        self.assertEqual(snapshot["path"], "/media")
        self.assertEqual(snapshot["parent"], "/")
        self.assertEqual(
            snapshot["directories"],
            [
                {"name": "alpha", "path": "/media/alpha"},
                {"name": "Zeta", "path": "/media/Zeta"},
            ],
        )
        self.assertEqual(len(snapshot["mounts"]), 5)
        self.assertTrue(snapshot["allMounted"])
        filesystem_calls = [
            call for call in self.client.calls
            if call[0] == "json" and "/filesystem?" in call[2]
        ]
        self.assertEqual(len(filesystem_calls), 5)
        self.assertTrue(all("includeFiles=false" in call[2] for call in filesystem_calls))

    def test_library_filesystem_browser_reports_service_errors_safely(self):
        sonarr_url = self.reconciler.settings.url("sonarr")
        self.client.filesystems[sonarr_url] = {
            "/missing": RequestError("filesystem unavailable", 503),
        }

        with self.assertRaisesRegex(ValueError, "Unable to browse Sonarr"):
            self.reconciler.browse_library_filesystem("sonarr", "/missing")

    def test_individual_library_rejects_a_path_missing_from_another_arr(self):
        self.reconciler.reconcile_async = lambda: True
        self.reconciler._setup_complete = True
        self.reconciler._setup_ready = True
        self.reconciler.save_storage("local", {})
        with self.assertRaisesRegex(ValueError, "Choose a system folder"):
            self.reconciler.save_library_storage("sonarr", "custom", path="")
        selected_path = "/media/shows"
        radarr_url = self.reconciler.settings.url("radarr")
        self.client.filesystems[radarr_url] = {
            selected_path: RequestError("Path is not mounted", 404),
        }

        with self.assertRaisesRegex(ValueError, "same path in every managed media service; check Radarr"):
            self.reconciler.save_library_storage(
                "sonarr", "custom", path=selected_path,
            )

        snapshot = self.reconciler.storage_snapshot()
        self.assertEqual(snapshot["roots"]["sonarr"], LOCAL_ROOTS["sonarr"])

    def test_qbittorrent_configures_proxy_and_five_categories(self):
        detail = self.reconciler.configure_qbittorrent(True)
        forms = [call for call in self.client.calls if call[0] == "form"]
        preferences = json.loads(forms[0][4]["json"])
        categories = [call[4]["category"] for call in forms[1:]]
        self.assertEqual(preferences["proxy_type"], "SOCKS5")
        self.assertEqual(preferences["proxy_ip"], "vpn")
        self.assertEqual(categories, ["movies", "movies-4k", "tv", "tv-4k", "music"])
        self.assertIn("five media categories", detail)

    def test_direct_provider_clears_owned_qbittorrent_proxy_fields(self):
        client = QbitAuthClient(active_password="umbrel-password")
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler._set_modules(
            {"prowlarr", "qbittorrent", "sonarr"}, "direct",
        )
        reconciler._qbit_login("admin", "umbrel-password")
        detail = reconciler.configure_qbittorrent(True)
        self.assertIn("direct routing", detail)
        self.assertEqual(client.preferences["proxy_type"], "None")
        self.assertEqual(client.preferences["proxy_ip"], "")
        self.assertFalse(client.preferences["proxy_bittorrent"])

    def test_direct_provider_clears_bazarr_proxy_with_null_sentinel(self):
        detail = self.reconciler.configure_bazarr(False)

        call = next(
            call for call in self.client.calls
            if call[0] == "form" and call[2].endswith("/api/system/settings")
        )
        values = call[4]
        self.assertEqual(values["settings-proxy-type"], "None")
        self.assertEqual(values["settings-proxy-url"], "")
        self.assertEqual(values["settings-proxy-port"], "")
        self.assertEqual(values["settings-proxy-exclude"], [])
        self.assertEqual(call[3], {"X-API-KEY": "bazarr-key"})
        self.assertEqual(detail, "HD Sonarr and Radarr are connected")

    def test_sabnzbd_uses_current_socks_setting(self):
        original_form = self.client.form

        def form(method, url, values, headers=None):
            if values.get("mode") == "get_config":
                self.client.calls.append(("form", method, url, headers, values))
                return Response(
                    200, {},
                    b'{"config":{"misc":{"host_whitelist":"existing.example"}}}',
                )
            return original_form(method, url, values, headers)

        self.client.form = form
        self.reconciler.configure_sabnzbd(True)
        forms = [call for call in self.client.calls if call[0] == "form"]
        settings = {call[4].get("keyword"): call[4].get("value") for call in forms}
        self.assertEqual(settings["socks5_proxy_url"], "socks5://vpn:1080")
        self.assertEqual(settings["host_whitelist"], "existing.example,sab")
        self.assertNotIn("socks5_proxy", settings)
        self.assertTrue(all(call[3] == {"Host": "localhost:8080"} for call in forms))

    def test_profilarr_forms_are_same_origin(self):
        self.client.json = lambda *_args, **_kwargs: []
        self.assertEqual(self.reconciler.configure_profilarr()[0], "waiting")
        call = next(call for call in self.client.calls if call[0] == "form")
        self.assertEqual(call[3]["Origin"], "http://profilarr:6868")
        self.assertEqual(call[3]["Referer"], "http://profilarr:6868/")

    def test_profilarr_marker_is_created_only_after_all_initial_syncs_are_accepted(self):
        client = ProfilarrClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.configure_profilarr()
        sync_calls = [call for call in client.calls if call[0] == "form" and "/sync?/syncQualityProfiles" in call[2]]
        self.assertEqual(len(sync_calls), 4)
        self.assertTrue(any(item.get("label") == PROFILARR_SYNC_MARKER_TAG for item in client.tags))
        reconciler.configure_profilarr()
        sync_calls = [call for call in client.calls if call[0] == "form" and "/sync?/syncQualityProfiles" in call[2]]
        self.assertEqual(len(sync_calls), 4)

    def test_profilarr_failed_initial_sync_does_not_create_marker(self):
        client = ProfilarrClient(fail_sync_id=3)
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        with self.assertRaises(RequestError):
            reconciler.configure_profilarr()
        self.assertFalse(any(item.get("label") == PROFILARR_SYNC_MARKER_TAG for item in client.tags))

    def test_overseerr_profile_preferences_are_deterministic(self):
        profiles = [{"id": 1, "name": "Any"}, {"id": 2, "name": "1080p Quality HDR"}, {"id": 3, "name": "2160p Quality"}]
        self.assertEqual(self.reconciler._overseerr_profile(profiles, False)["id"], 2)
        self.assertEqual(self.reconciler._overseerr_profile(profiles, True)["id"], 3)

    def test_servarr_configuration_is_idempotent(self):
        client = StackClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        arr = reconciler.arrs[2]
        reconciler.configure_arr(arr)
        qbittorrent = next(item for item in client.clients if item["name"] == "Umbrel Arr qBittorrent")
        qbittorrent["fields"].append({"name": "userOwnedSetting", "value": "preserve-me"})
        put_count = sum(call[1] == "PUT" for call in client.calls)
        reconciler.configure_arr(arr)
        self.assertEqual(client.roots, [{"path": "/downloads/movies", "id": 1}])
        self.assertEqual(len(client.clients), 2)
        self.assertEqual({item["name"] for item in client.clients}, {"Umbrel Arr qBittorrent", "Umbrel Arr SABnzbd"})
        self.assertEqual(sum(call[1] == "PUT" for call in client.calls), put_count)
        fields = {field["name"]: field["value"] for field in qbittorrent["fields"]}
        self.assertEqual(fields["username"], "admin")
        self.assertEqual(fields["password"], "umbrel-password")
        self.assertEqual(fields["userOwnedSetting"], "preserve-me")

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

    def test_prelogin_reconciliation_waits_without_false_failures(self):
        reconciler = Reconciler(Settings(environment(self.temp.name)), self.client)
        reconciler._setup_complete = True
        reconciler._setup_ready = True
        reconciler.configure_storage = lambda: "Storage ready"
        reconciler.check_vpn = lambda: ("action_required", "Enter Privado login")
        reconciler.check_flaresolverr = lambda: self.fail("FlareSolverr should wait for VPN")
        reconciler.configure_qbittorrent = lambda _vpn_ok: ("waiting", "Waiting for VPN")
        reconciler.configure_sabnzbd = lambda _vpn_ok: ("waiting", "Waiting for VPN")
        reconciler.configure_arr = lambda _arr: self.fail("Arr apps should wait for download clients")
        reconciler.configure_prowlarr = lambda _vpn_ok: self.fail("Prowlarr should wait for VPN")
        reconciler.configure_bazarr = lambda _vpn_ok: self.fail("Bazarr should wait for VPN")
        reconciler.configure_profilarr = lambda: "Profilarr ready"
        reconciler.configure_overseerr = lambda: ("action_required", "Complete Plex sign-in")

        reconciler.reconcile()

        snapshot = reconciler.runtime.snapshot()
        services = {service["id"]: service for service in snapshot["services"]}
        waiting = {"flaresolverr", "prowlarr", "qbittorrent", "sabnzbd", "bazarr", *(arr.slug for arr in reconciler.arrs)}
        self.assertTrue(all(services[slug]["status"] == "waiting" for slug in waiting))
        self.assertEqual(snapshot["counts"]["failed"], 0)

    def test_dependency_graph_matches_reconciliation_prerequisites(self):
        self.assertEqual(DEPENDENCIES["flaresolverr"], ("privado-vpn",))
        self.assertEqual(DEPENDENCIES["qbittorrent"], ("privado-vpn",))
        self.assertEqual(DEPENDENCIES["sonarr"], ("umbrelarr", "qbittorrent", "sabnzbd"))
        self.assertIn("flaresolverr", DEPENDENCIES["prowlarr"])
        self.assertEqual(DEPENDENCIES["bazarr"], ("privado-vpn", "sonarr", "radarr"))

    def test_missing_bazarr_key_waits_for_app_persistence(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_BAZARR_API_KEY"] = ""
        reconciler = Reconciler(Settings(values), self.client)
        self.assertEqual(
            reconciler.configure_bazarr(True),
            ("waiting", "Waiting for Bazarr to persist its API key"),
        )

    def test_prowlarr_configuration_is_idempotent(self):
        client = StackClient()
        reconciler = Reconciler(Settings(environment(self.temp.name)), client)
        reconciler.configure_prowlarr(True)
        client.proxies[0]["fields"].append({"name": "userOwnedSetting", "value": "preserve-me"})
        client.applications[0]["fields"].append({"name": "userOwnedSetting", "value": "preserve-me"})
        client.host_config["userOwnedSetting"] = "preserve-me"
        put_count = sum(call[1] == "PUT" for call in client.calls)
        reconciler.configure_prowlarr(True)
        self.assertEqual(client.tags, [{"label": "flaresolverr", "id": 1}])
        self.assertEqual(len(client.proxies), 1)
        self.assertEqual(client.proxies[0]["tags"], [1])
        self.assertEqual(len(client.applications), 5)
        self.assertEqual(sum(call[1] == "PUT" for call in client.calls), put_count)
        self.assertTrue(client.host_config["proxyEnabled"])
        self.assertEqual(client.host_config["proxyType"], "socks5")
        self.assertEqual(client.host_config["userOwnedSetting"], "preserve-me")
        proxy_fields = {field["name"]: field["value"] for field in client.proxies[0]["fields"]}
        app_fields = {field["name"]: field["value"] for field in client.applications[0]["fields"]}
        self.assertEqual(proxy_fields["userOwnedSetting"], "preserve-me")
        self.assertEqual(app_fields["userOwnedSetting"], "preserve-me")

    def test_errors_redact_secrets(self):
        safe = self.reconciler._safe_error(RuntimeError("password=hunter2 token=abc api_key=xyz"))
        self.assertNotIn("hunter2", safe)
        self.assertNotIn("abc", safe)
        self.assertNotIn("xyz", safe)
        json_safe = self.reconciler._safe_error(RuntimeError('{"password":"fresh-secret","apiKey":"key-secret"}'))
        self.assertNotIn("fresh-secret", json_safe)
        self.assertNotIn("key-secret", json_safe)
        secret = "unique-runtime-secret-938"
        self.reconciler._step(
            "qbittorrent",
            lambda: (_ for _ in ()).throw(RuntimeError(f'{{"password":"{secret}"}}')),
        )
        rendered = json.dumps(self.reconciler.runtime.snapshot())
        self.assertNotIn(secret, rendered)

    def test_mutating_http_endpoints_share_the_setup_gate(self):
        import app as web_app
        previous = web_app.RECONCILER
        web_app.RECONCILER = self.reconciler
        try:
            with self.assertRaisesRegex(RuntimeError, "Complete explicit setup"):
                web_app.Handler._require_setup()
            self.reconciler._setup_complete = True
            with self.assertRaisesRegex(RuntimeError, "Complete explicit setup"):
                web_app.Handler._require_setup()
            self.reconciler._setup_ready = True
            web_app.Handler._require_setup()
        finally:
            web_app.RECONCILER = previous


class StateTests(unittest.TestCase):
    def test_runtime_state_counts_explicit_unknowns(self):
        state = RuntimeState([ServiceStatus("one", "One"), ServiceStatus("two", "Two")])
        state.set("one", "healthy", "Ready")
        snapshot = state.snapshot()
        self.assertEqual(snapshot["counts"]["healthy"], 1)
        self.assertEqual(snapshot["counts"]["unknown"], 1)

    def test_runtime_state_reports_current_upstream_blockers(self):
        state = RuntimeState(
            [ServiceStatus("vpn", "VPN"), ServiceStatus("client", "Client")],
            {"vpn": (), "client": ("vpn",)},
        )
        state.set("vpn", "waiting", "Connecting")
        state.set("client", "waiting", "Waiting for VPN")
        services = {service["id"]: service for service in state.snapshot()["services"]}
        self.assertEqual(services["client"]["dependencies"], ["vpn"])
        self.assertEqual(services["client"]["waitingOn"], ["vpn"])
        state.set("vpn", "healthy", "Ready")
        services = {service["id"]: service for service in state.snapshot()["services"]}
        self.assertEqual(services["client"]["waitingOn"], [])

    def test_runtime_state_keeps_bounded_check_history(self):
        state = RuntimeState([ServiceStatus("one", "One", role="control_plane")])
        for index in range(30):
            state.set("one", "healthy" if index % 2 else "waiting", f"Check {index}")
        service = state.snapshot()["services"][0]
        self.assertEqual(service["role"], "control_plane")
        self.assertEqual(len(service["checks"]), 24)
        self.assertEqual(service["checks"][-1]["status"], "healthy")

    def test_runtime_state_exposes_authenticated_resource_snapshots(self):
        state = RuntimeState([ServiceStatus("one", "One")])
        state.set_container("one", {
            "state": "running", "health": "healthy", "updatedAt": 41,
        })
        state.set_resources("one", {"updatedAt": 42, "cpu": {"percent": 31}})
        service = state.snapshot()["services"][0]
        self.assertEqual(service["container"]["state"], "running")
        self.assertEqual(service["resources"]["updatedAt"], 42)
        self.assertEqual(service["resources"]["cpu"]["percent"], 31)

    def test_runtime_state_retains_last_real_resource_sample(self):
        state = RuntimeState([ServiceStatus("one", "One")])
        state.set_resources("one", {
            "source": "docker",
            "updatedAt": 42,
            "sampleState": "current",
            "cpu": {"percent": 31},
        })

        state.retain_resources("one")

        resources = state.snapshot()["services"][0]["resources"]
        self.assertEqual(resources["sampleState"], "last_sample")
        self.assertEqual(resources["updatedAt"], 42)
        self.assertEqual(resources["cpu"]["percent"], 31)

    def test_runtime_state_does_not_invent_a_resource_sample_timestamp(self):
        state = RuntimeState([ServiceStatus("one", "One")])

        state.retain_resources("one")

        resources = state.snapshot()["services"][0]["resources"]
        self.assertEqual(resources["sampleState"], "unavailable")
        self.assertNotIn("updatedAt", resources)

    def test_storage_is_derived_from_api_root_ids_without_files(self):
        storage = StorageSettings()
        storage.set_enabled_modules({*LOCAL_ROOTS, "jellyfin", "plex"})
        folders = {
            slug: [{"id": index + 10, "path": path}]
            for index, (slug, path) in enumerate(NETWORK_ROOTS.items())
        }
        snapshot = storage.update_from_apis(folders)
        self.assertEqual(snapshot["mode"], "network")
        self.assertEqual(snapshot["roots"], NETWORK_ROOTS)
        self.assertFalse(snapshot["actionRequired"])
        self.assertEqual(len(snapshot["libraries"]), 5)
        self.assertEqual(snapshot["libraries"][0]["source"], "network")
        self.assertEqual(snapshot["libraries"][0]["rootId"], 10)
        self.assertEqual(snapshot["libraries"][0]["candidates"], folders["sonarr"])
        self.assertIn("overseerr", LIBRARY_DEFINITIONS["radarr-4k"]["apps"])
        self.assertIn("jellyfin", snapshot["libraries"][0]["apps"])
        self.assertIn("plex", snapshot["libraries"][0]["apps"])

    def test_multiple_existing_roots_require_an_explicit_api_selection(self):
        storage = StorageSettings()
        folders = {
            slug: [
                {"id": 1, "path": LOCAL_ROOTS[slug]},
                {"id": 2, "path": NETWORK_ROOTS[slug]},
            ]
            for slug in LOCAL_ROOTS
        }
        snapshot = storage.update_from_apis(folders)
        self.assertEqual(snapshot["mode"], "adopted")
        self.assertTrue(snapshot["actionRequired"])
        selected = storage.update_from_apis(folders, "adopted", {slug: 2 for slug in folders})
        self.assertEqual(selected["roots"], NETWORK_ROOTS)
        self.assertFalse(selected["actionRequired"])


class ApiKeyResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.resolver = ApiKeyResolver(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def test_extracts_every_supported_app_key_format(self):
        for slug in ("prowlarr", "sonarr", "sonarr-4k", "radarr", "radarr-4k", "lidarr"):
            self.write(f"{slug}/config.xml", f"<Config><ApiKey>{slug}-generated-key-123456</ApiKey></Config>")
        self.write("sabnzbd/sabnzbd.ini", "__encoding__ = utf-8\n[misc]\napi_key = sabnzbd-generated-key-123456\n")
        self.write("bazarr/config/config.yaml", "auth:\n  apikey: bazarr-generated-key-123456\ngeneral:\n  flask_secret_key: ignored\n")
        self.write("overseerr/settings.json", json.dumps({"main": {"apiKey": "overseerr-generated-key-123456"}}))
        jellyfin_db = self.root / "jellyfin/data/jellyfin.db"
        jellyfin_db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(jellyfin_db)
        try:
            with connection:
                connection.execute('CREATE TABLE "ApiKeys" ("Name" TEXT, "AccessToken" TEXT)')
                connection.execute(
                    'INSERT INTO "ApiKeys" ("Name", "AccessToken") VALUES (?, ?)',
                    ("another-app", "do-not-adopt-this-key"),
                )
                connection.execute(
                    'INSERT INTO "ApiKeys" ("Name", "AccessToken") VALUES (?, ?)',
                    ("umbrelarr", "jellyfin-generated-key-123456"),
                )
        finally:
            connection.close()
        self.write(
            "plex/Library/Application Support/Plex Media Server/Preferences.xml",
            '<Preferences FriendlyName="Umbrel" PlexOnlineToken="plex-generated-token-123456"/>',
        )

        expected = {
            "prowlarr", "sonarr", "sonarr-4k", "radarr", "radarr-4k", "lidarr",
            "sabnzbd", "bazarr", "overseerr", "jellyfin", "plex",
        }
        self.assertEqual({slug for slug in expected if self.resolver.resolve(slug)}, expected)
        self.assertEqual(self.resolver.resolve("bazarr"), "bazarr-generated-key-123456")
        self.assertEqual(self.resolver.resolve("overseerr"), "overseerr-generated-key-123456")
        self.assertEqual(self.resolver.resolve("jellyfin"), "jellyfin-generated-key-123456")
        self.assertEqual(self.resolver.resolve("plex"), "plex-generated-token-123456")

    def test_missing_malformed_and_unsupported_sources_are_safe(self):
        self.write("sonarr/config.xml", "<Config><ApiKey>")
        self.write("overseerr/settings.json", "not-json")
        self.assertEqual(self.resolver.resolve("sonarr"), "")
        self.assertEqual(self.resolver.resolve("overseerr"), "")
        self.assertEqual(self.resolver.resolve("qbittorrent"), "")


class DashboardTests(unittest.TestCase):
    def test_dashboard_is_operational_and_accessible(self):
        self.assertIn("<title>umbrelarr</title>", PAGE)
        self.assertIn('rel="icon" href="/icon.png"', PAGE)
        self.assertIn('<img src="/icon.png" alt="">', PAGE)
        self.assertIn("Privado login required", PAGE)
        self.assertIn("aria-label=\"Stack summary\"", PAGE)
        self.assertIn("aria-label=\"Primary navigation\"", PAGE)
        self.assertIn('href="/libraries"', PAGE)
        self.assertNotIn('href="/dependencies"', PAGE)
        self.assertNotIn('class="nav-label"', PAGE)
        self.assertIn("Reconcile", PAGE)
        self.assertIn("@media (max-width: 560px)", PAGE)
        for status in ("unknown", "waiting", "action_required", "configuring", "healthy", "failed"):
            self.assertIn(status, PAGE)
        self.assertIn("color-scheme: dark", PAGE)
        self.assertIn("--sidebar: #070b10", PAGE)
        self.assertIn("--canvas: #0a0f15", PAGE)
        self.assertIn("--primary: #50d890", PAGE)
        self.assertIn('class="nav-icon" aria-hidden="true"><svg', PAGE)
        self.assertNotIn("radial-gradient", PAGE)
        self.assertIn("border-radius: 10px", PAGE)
        self.assertIn("prefers-reduced-motion", PAGE)
        self.assertIn("/service-icons/", PAGE)
        self.assertIn("service.id==='umbrelarr'?'/icon.png'", PAGE)
        self.assertIn("Resources", PAGE)
        self.assertIn('role="meter" aria-valuemin="0"', PAGE)
        self.assertNotIn("API-derived health · 24-check window", PAGE)
        self.assertIn("chooseService", PAGE)
        self.assertIn("showModal", PAGE)
        self.assertIn("data-module-action", PAGE)

    def test_dashboard_routes_render_only_their_task(self):
        services = render_page("services")
        libraries = render_page("libraries")
        activity = render_page("activity")
        with self.assertRaises(ValueError):
            render_page("setup")
        with self.assertRaises(ValueError):
            render_page("dependencies")
        self.assertNotIn('href="/setup"', services)
        self.assertIn('id="serviceGrid"', services)
        self.assertIn('id="serviceSearch"', services)
        self.assertIn('id="manageServices"', services)
        self.assertIn('id="serviceManager"', services)
        self.assertIn('id="detectApps"', services)
        self.assertIn('id="confirmSetup"', services)
        self.assertIn('id="cancelServiceChanges"', services)
        self.assertIn('id="removeServiceDialog"', services)
        self.assertIn('id="confirmRemoveService"', services)
        self.assertIn('data-remove-service', services)
        self.assertIn('/api/setup/remove', services)
        self.assertIn("Add one service", services)
        self.assertIn('aria-haspopup="dialog"', services)
        self.assertIn("Choose one installed service", services)
        self.assertIn('id="directConnections"', services)
        self.assertIn('id="jellyfinCredentialBootstrap"', services)
        self.assertIn('id="bootstrapJellyfinCredential"', services)
        self.assertIn('/api/setup/credentials/bootstrap', services)
        self.assertIn('Connected automatically', services)
        self.assertNotIn("Continue on Umbrel", services)
        self.assertNotIn('id="stackProfile"', services)
        self.assertNotIn("Routing and storage", services)
        self.assertNotIn('id="vpnProvider"', services)
        self.assertNotIn("Add or remove services", services)
        self.assertNotIn("does not uninstall the app or delete that app's settings", services)
        self.assertNotIn('/api/containers', services)
        self.assertNotIn('<tbody id="serviceRows">', services)
        self.assertNotIn('href="/containers"', services)
        self.assertNotIn('id="storageForm"', services)
        self.assertNotIn('href="/services/${encodeURIComponent(service.id)}"', services)
        self.assertIn('id="libraryGrid"', libraries)
        self.assertIn("Your media libraries", libraries)
        self.assertNotIn("Configuration level", libraries)
        self.assertNotIn("Basic", libraries)
        self.assertNotIn("Expert", libraries)
        self.assertNotIn("Apply libraries to managed apps", libraries)
        self.assertNotIn('id="serviceGrid"', libraries)
        self.assertIn('id="events"', activity)
        self.assertNotIn('id="storageForm"', activity)

    def test_library_detail_exposes_complete_per_library_configuration(self):
        detail = render_page("library", library_id="tv")
        self.assertIn('data-library-id="tv"', detail)
        self.assertIn('id="libraryForm"', detail)
        self.assertIn('name="librarySource" value="local"', detail)
        self.assertIn('name="librarySource" value="network"', detail)
        self.assertIn('name="librarySource" value="custom"', detail)
        self.assertIn('id="libraryBrowser"', detail)
        self.assertIn('id="libraryMountCheck"', detail)
        self.assertIn('id="libraryPath"', detail)
        self.assertNotIn('id="libraryRootId"', detail)
        self.assertNotIn("API only", detail)
        self.assertNotIn("Choose where this library lives", detail)
        self.assertIn("Managed configuration", detail)
        self.assertIn('aria-current="page" href="/libraries"', detail)
        self.assertNotIn("Basic", detail)
        self.assertNotIn("Expert", detail)
        with self.assertRaisesRegex(ValueError, "Unknown managed library"):
            render_page("library", library_id="not-owned")


class ImageTests(unittest.TestCase):
    def test_image_uses_the_shared_media_uid(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("adduser -S -D -H -u 1000", dockerfile)
        self.assertIn("USER umbrelarr", dockerfile)

    def test_web_control_plane_has_no_docker_socket_or_persistent_state(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        app = (ROOT / "app" / "app.py").read_text()
        broker = (ROOT / "app" / "docker_inventory.py").read_text()
        self.assertNotIn("/data", dockerfile)
        self.assertNotIn("STATE_DIR", dockerfile)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", dockerfile)
        self.assertIn("docker_inventory.py", dockerfile)
        self.assertIn("COPY app/service-icons ./service-icons", dockerfile)
        self.assertNotIn("docker.sock", dockerfile)
        self.assertNotIn("DockerEngineClient", app)
        self.assertIn("class DockerInventory", broker)
        self.assertFalse((ROOT / "app" / "containers.py").exists())
        self.assertFalse((ROOT / "compose.local.yml").exists())

    def test_runtime_sources_do_not_write_files(self):
        sources = "\n".join(path.read_text() for path in (ROOT / "app").glob("*.py"))
        for mutation in (".mkdir(", ".write_text(", ".write_bytes(", ".unlink("):
            self.assertNotIn(mutation, sources)


if __name__ == "__main__":
    unittest.main()
