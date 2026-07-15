import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "app"
ROOT = SOURCE.parent
sys.path.insert(0, str(SOURCE))

from dashboard import PAGE, render_page
from api_keys import ApiKeyResolver
from catalog import CORE_MODULES, STACK_PROFILES, dependencies_for, normalize_modules, validate_modules
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
        "UMBREL_ARR_QBITTORRENT_PASSWORD": "umbrel-password",
    }
    for slug in ("prowlarr", "sabnzbd", "sonarr", "sonarr_4k", "radarr", "radarr_4k", "bazarr", "overseerr", "lidarr"):
        values[f"UMBREL_ARR_{slug.upper()}_API_KEY"] = f"{slug}-key"
    return values


class FakeClient:
    def __init__(self):
        self.calls = []
        self.vpn = {"credentialsConfigured": False, "state": "down"}
        self.tags = []
        self.roots = {}

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
        if url.endswith("/api/v1/tag"):
            if method == "POST":
                item = {**payload, "id": len(self.tags) + 1}
                self.tags.append(item)
                return item
            return [dict(item) for item in self.tags]
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

    def test_module_catalog_derives_dependencies_from_selection(self):
        selected = {"umbrelarr", "prowlarr", "qbittorrent", "sonarr"}
        dependencies = dependencies_for(selected)
        self.assertEqual(dependencies["sonarr"], ("umbrelarr", "qbittorrent"))
        self.assertEqual(dependencies["prowlarr"], ("sonarr",))
        self.assertNotIn("privado-vpn", dependencies)
        self.assertEqual(validate_modules({"bazarr"}), ["Bazarr requires Sonarr and Radarr"])
        self.assertTrue(CORE_MODULES <= set(selected))

    def test_every_starting_profile_is_valid_and_keeps_the_required_core(self):
        profiles = {profile.id: profile for profile in STACK_PROFILES}
        self.assertEqual(set(profiles), {"core", "tv-torrent", "video-usenet", "full"})
        for profile in profiles.values():
            selected = normalize_modules(profile.enabled_services)
            self.assertTrue(CORE_MODULES <= selected, profile.id)
            self.assertEqual(validate_modules(selected), [], profile.id)
        self.assertEqual(
            normalize_modules(profiles["tv-torrent"].enabled_services),
            frozenset({"umbrelarr", "prowlarr", "qbittorrent", "sonarr"}),
        )

    def test_selected_modules_limit_read_only_detection(self):
        snapshot = self.reconciler.select_and_detect(
            ["prowlarr", "sonarr", "qbittorrent"], "direct",
        )
        self.assertEqual(snapshot["vpnProvider"], "direct")
        self.assertEqual(snapshot["requiredCount"], 3)
        self.assertEqual(
            {item["id"] for item in snapshot["apps"]},
            {"prowlarr", "sonarr", "qbittorrent"},
        )
        self.assertNotIn("privado-vpn", self.reconciler.enabled_modules)
        requests = [call for call in self.client.calls if call[0] == "request"]
        self.assertEqual(len(requests), 3)
        self.assertTrue(all(call[1] == "GET" for call in requests))

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

        snapshot = reconciler.select_and_detect(["prowlarr", "sonarr"], "direct")

        self.assertTrue(snapshot["configurationChanged"])
        self.assertEqual(snapshot["phase"], "ready")
        self.assertTrue(snapshot["canConfirm"])
        self.assertEqual(snapshot["vpnProvider"], "direct")

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
        self.assertEqual(len(requests), len(REQUIRED_APPS))
        self.assertTrue(all(call[1] == "GET" for call in requests))
        self.assertFalse(any(call[1] in {"POST", "PUT", "DELETE"} for call in self.client.calls))
        self.assertTrue(all({"reachable", "credentials", "action"} <= item.keys() for item in snapshot["apps"]))

    def test_confirmation_rejects_missing_storage_choice(self):
        self.reconciler.detect_apps()
        with self.assertRaisesRegex(ValueError, "Choose local"):
            self.reconciler.confirm_setup()
        self.assertFalse(any(item.get("label") == SETUP_MARKER_TAG for item in self.client.tags))

    def test_confirmation_rejects_missing_generated_api_key(self):
        values = environment(self.temp.name)
        values["UMBREL_ARR_SONARR_API_KEY"] = ""
        reconciler = Reconciler(Settings(values), self.client)
        snapshot = reconciler.detect_apps()
        self.assertFalse(snapshot["canConfirm"])
        sonarr = next(item for item in snapshot["apps"] if item["id"] == "sonarr")
        self.assertIn("Restart umbrelarr", sonarr["detail"])
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
        reconciler.configure_arr(arr)
        self.assertEqual(client.roots, [{"path": "/downloads/movies", "id": 1}])
        self.assertEqual(len(client.clients), 2)
        self.assertEqual({item["name"] for item in client.clients}, {"Umbrel Arr qBittorrent", "Umbrel Arr SABnzbd"})
        qbittorrent = next(item for item in client.clients if item["name"] == "Umbrel Arr qBittorrent")
        fields = {field["name"]: field["value"] for field in qbittorrent["fields"]}
        self.assertEqual(fields["username"], "admin")
        self.assertEqual(fields["password"], "umbrel-password")

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

    def test_storage_is_derived_from_api_root_ids_without_files(self):
        storage = StorageSettings()
        folders = {
            slug: [{"id": index + 10, "path": path}]
            for index, (slug, path) in enumerate(NETWORK_ROOTS.items())
        }
        snapshot = storage.update_from_apis(folders)
        self.assertEqual(snapshot["mode"], "network")
        self.assertEqual(snapshot["roots"], NETWORK_ROOTS)
        self.assertFalse(snapshot["actionRequired"])
        self.assertEqual(len(snapshot["libraries"]), 5)
        self.assertIn("overseerr", LIBRARY_DEFINITIONS["radarr-4k"]["apps"])

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

        expected = {
            "prowlarr", "sonarr", "sonarr-4k", "radarr", "radarr-4k", "lidarr",
            "sabnzbd", "bazarr", "overseerr",
        }
        self.assertEqual({slug for slug in expected if self.resolver.resolve(slug)}, expected)
        self.assertEqual(self.resolver.resolve("bazarr"), "bazarr-generated-key-123456")
        self.assertEqual(self.resolver.resolve("overseerr"), "overseerr-generated-key-123456")

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
        self.assertIn("Reconcile", PAGE)
        self.assertIn("@media (max-width: 560px)", PAGE)
        for status in ("unknown", "waiting", "action_required", "configuring", "healthy", "failed"):
            self.assertIn(status, PAGE)
        self.assertIn("--sidebar: #20242a", PAGE)
        self.assertIn("--canvas: #f5f6f8", PAGE)
        self.assertIn("--primary: #2e8b57", PAGE)
        self.assertNotIn("radial-gradient", PAGE)
        self.assertIn("border-radius: 10px", PAGE)
        self.assertIn("prefers-reduced-motion", PAGE)

    def test_dashboard_routes_render_only_their_task(self):
        setup = render_page("setup")
        services = render_page("services")
        service = render_page("service", service_id="sonarr")
        dependencies = render_page("dependencies")
        libraries = render_page("libraries")
        activity = render_page("activity")
        self.assertIn('id="detectApps"', setup)
        self.assertIn('id="confirmSetup"', setup)
        self.assertIn("does not create containers", setup)
        self.assertIn('aria-current="page" href="/setup"', setup)
        self.assertIn('id="serviceGrid"', services)
        self.assertIn('id="serviceSearch"', services)
        self.assertNotIn('/api/containers', services)
        self.assertNotIn('<tbody id="serviceRows">', services)
        self.assertNotIn('href="/containers"', services)
        self.assertNotIn('id="storageForm"', services)
        self.assertIn('data-service-id="sonarr"', service)
        self.assertIn('id="detailDependencies"', service)
        self.assertNotIn('id="containerLogs"', service)
        self.assertIn('aria-current="page" href="/services"', service)
        self.assertIn('id="dependencyGraph"', dependencies)
        self.assertIn('id="dependencyRows"', dependencies)
        self.assertNotIn('id="serviceGrid"', dependencies)
        self.assertIn('id="storageForm"', libraries)
        self.assertIn('id="libraryPlan"', libraries)
        self.assertIn("Reconcile scope", libraries)
        self.assertIn("Save library layout", libraries)
        self.assertNotIn("Apply libraries to managed apps", libraries)
        self.assertNotIn('id="serviceGrid"', libraries)
        self.assertIn('id="events"', activity)
        self.assertNotIn('id="storageForm"', activity)

    def test_unknown_service_detail_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown managed service"):
            render_page("service", service_id="not-owned")

    def test_library_settings_have_basic_and_expert_modes(self):
        basic = render_page("libraries", "basic")
        expert = render_page("libraries", "expert")
        self.assertIn("Basic mode applies a complete, safe five-library layout", basic)
        self.assertIn('data-level="basic"', basic)
        self.assertIn('value="adopt"', basic)
        self.assertIn('id="storageRootSelections"', basic)
        self.assertIn('aria-current="page" href="/libraries"', basic)
        self.assertIn("Expert mode can adopt one existing API-reported root ID", expert)
        self.assertIn('data-level="expert"', expert)
        self.assertNotIn('name="sonarr" required', expert)
        self.assertNotIn("/api/containers", expert)


class ImageTests(unittest.TestCase):
    def test_image_uses_the_shared_media_uid(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("adduser -S -D -H -u 1000", dockerfile)
        self.assertIn("USER umbrelarr", dockerfile)

    def test_control_plane_has_no_docker_socket_or_persistent_state(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        app = (ROOT / "app" / "app.py").read_text()
        self.assertNotIn("/data", dockerfile)
        self.assertNotIn("STATE_DIR", dockerfile)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", dockerfile)
        self.assertNotIn("containers", app)
        self.assertFalse((ROOT / "app" / "containers.py").exists())
        self.assertFalse((ROOT / "compose.local.yml").exists())

    def test_runtime_sources_do_not_write_files(self):
        sources = "\n".join(path.read_text() for path in (ROOT / "app").glob("*.py"))
        for mutation in (".mkdir(", ".write_text(", ".write_bytes(", ".unlink("):
            self.assertNotIn(mutation, sources)


if __name__ == "__main__":
    unittest.main()
