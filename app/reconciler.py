import copy
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from api_keys import ApiKeyResolver
from http_client import HttpClient, RequestError
from state import RuntimeState, ServiceStatus
from storage import LOCAL_ROOTS, PRESETS, StorageSettings


MANAGED_TAG = "umbrel-arr-managed"
SETUP_MARKER_TAG = "umbrel-arr-setup-complete"
SETUP_READY_MARKER_TAG = "umbrel-arr-setup-ready-v1"
PROFILARR_SYNC_MARKER_TAG = "umbrel-arr-profilarr-initial-sync-v1"
STORAGE_MARKER_PREFIX = "umbrel-arr-storage-"
DATABASE_URL = "https://github.com/Dictionarry-Hub/database"
HD_PROFILES = ["1080p Compact", "1080p Efficient", "1080p Quality HDR"]
UHD_PROFILES = ["2160p Efficient", "2160p Quality"]


APP_PORTS = {
    "privado-vpn": 30980,
    "flaresolverr": 30981,
    "prowlarr": 30982,
    "qbittorrent": 30983,
    "sabnzbd": 30984,
    "sonarr": 30985,
    "sonarr-4k": 30986,
    "radarr": 30987,
    "radarr-4k": 30988,
    "bazarr": 30989,
    "overseerr": 30990,
    "profilarr": 30991,
    "umbrelarr": 30992,
    "lidarr": 30993,
}


NAMES = {
    "privado-vpn": "Privado VPN",
    "flaresolverr": "FlareSolverr",
    "prowlarr": "Prowlarr",
    "qbittorrent": "qBittorrent",
    "sabnzbd": "SABnzbd",
    "sonarr": "Sonarr",
    "sonarr-4k": "Sonarr 4K",
    "radarr": "Radarr",
    "radarr-4k": "Radarr 4K",
    "bazarr": "Bazarr",
    "overseerr": "Overseerr",
    "profilarr": "Profilarr",
    "umbrelarr": "umbrelarr",
    "lidarr": "Lidarr",
}


MEDIA_APPS = ("sonarr", "sonarr-4k", "radarr", "radarr-4k", "lidarr")
HD_UHD_VIDEO_APPS = ("sonarr", "sonarr-4k", "radarr", "radarr-4k")
REQUIRED_APPS = tuple(slug for slug in NAMES if slug != "umbrelarr")
KEYED_APPS = {
    "prowlarr", "sabnzbd", "sonarr", "sonarr-4k", "radarr", "radarr-4k",
    "bazarr", "overseerr", "lidarr",
}
DEPENDENCIES = {
    "umbrelarr": (),
    "privado-vpn": (),
    "flaresolverr": ("privado-vpn",),
    "qbittorrent": ("privado-vpn",),
    "sabnzbd": ("privado-vpn",),
    **{
        slug: ("umbrelarr", "qbittorrent", "sabnzbd")
        for slug in MEDIA_APPS
    },
    "prowlarr": ("privado-vpn", "flaresolverr", *MEDIA_APPS),
    "bazarr": ("privado-vpn", "sonarr", "radarr"),
    "profilarr": HD_UHD_VIDEO_APPS,
    "overseerr": HD_UHD_VIDEO_APPS,
}


@dataclass
class ArrInstance:
    slug: str
    name: str
    implementation: str
    url: str
    api_key: str
    api_version: str
    root: str
    category: str
    external_port: int
    is_4k: bool = False

    @property
    def api(self):
        return f"{self.url.rstrip('/')}/api/{self.api_version}"


class Settings:
    def __init__(self, environ=None):
        env = environ or os.environ
        self.env = env
        self.device_domain = env.get("DEVICE_DOMAIN_NAME", "umbrel.local")
        self.interval = max(30, int(env.get("RECONCILE_INTERVAL", "300")))
        self.api_keys = ApiKeyResolver(env.get("UMBREL_ARR_MANAGED_CONFIG_DIR", "/managed-config"))

    def url(self, slug):
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_URL"
        return self.env.get(key, "").rstrip("/")

    def key(self, slug):
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_API_KEY"
        exported = self.env.get(key, "").strip()
        return exported or self.api_keys.resolve(slug)

    def external_url(self, slug):
        return f"http://{self.device_domain}:{APP_PORTS[slug]}"

    @property
    def qbittorrent_password(self):
        return self.env.get("UMBREL_ARR_QBITTORRENT_PASSWORD", "")


class Reconciler:
    def __init__(self, settings=None, client=None):
        self.settings = settings or Settings()
        self.client = client or HttpClient()
        services = [
            ServiceStatus(slug, NAMES[slug], link=self.settings.external_url(slug))
            for slug in NAMES
        ]
        self.runtime = RuntimeState(services, DEPENDENCIES)
        self.storage = StorageSettings()
        self.arrs = self._arr_instances()
        self._setup_lock = threading.RLock()
        self._setup_complete = False
        self._setup_ready = False
        self._setup_detection = []
        self._qbittorrent_cookie = ""
        self._mark_setup_required()

    def _arr_instances(self):
        return [
            ArrInstance("sonarr", "Sonarr", "Sonarr", self.settings.url("sonarr"), self.settings.key("sonarr"), "v3", self.storage.root("sonarr"), "tv", 30985),
            ArrInstance("sonarr-4k", "Sonarr 4K", "Sonarr", self.settings.url("sonarr-4k"), self.settings.key("sonarr-4k"), "v3", self.storage.root("sonarr-4k"), "tv-4k", 30986, True),
            ArrInstance("radarr", "Radarr", "Radarr", self.settings.url("radarr"), self.settings.key("radarr"), "v3", self.storage.root("radarr"), "movies", 30987),
            ArrInstance("radarr-4k", "Radarr 4K", "Radarr", self.settings.url("radarr-4k"), self.settings.key("radarr-4k"), "v3", self.storage.root("radarr-4k"), "movies-4k", 30988, True),
            ArrInstance("lidarr", "Lidarr", "Lidarr", self.settings.url("lidarr"), self.settings.key("lidarr"), "v1", self.storage.root("lidarr"), "music", 30993),
        ]

    def reconcile_async(self):
        if not self.ensure_setup_ready():
            raise RuntimeError("Complete app discovery and connection setup before reconciling")
        if self.runtime.running:
            return False
        threading.Thread(target=self.reconcile, name="reconcile", daemon=True).start()
        return True

    def reconcile(self):
        if not self.ensure_setup_ready():
            self._mark_setup_required()
            return
        if not self.runtime.begin():
            return
        self.arrs = self._arr_instances()
        self.runtime.event("Reconciliation started")
        try:
            storage_ok = self._step("umbrelarr", self.configure_storage)
            vpn_ok = self._step("privado-vpn", self.check_vpn)
            if vpn_ok:
                flaresolverr_ok = self._step("flaresolverr", self.check_flaresolverr)
            else:
                flaresolverr_ok = False
                self.runtime.set("flaresolverr", "waiting", "Waiting for a healthy Privado tunnel")
            qbittorrent_ok = self._step("qbittorrent", self.configure_qbittorrent, vpn_ok)
            sabnzbd_ok = self._step("sabnzbd", self.configure_sabnzbd, vpn_ok)
            if storage_ok and qbittorrent_ok and sabnzbd_ok:
                for arr in self.arrs:
                    self._step(arr.slug, self.configure_arr, arr)
            elif not storage_ok:
                for arr in self.arrs:
                    self.runtime.set(arr.slug, "waiting", "Waiting for writable network media storage")
            else:
                for arr in self.arrs:
                    self.runtime.set(arr.slug, "waiting", "Waiting for Privado-routed download clients")
            if vpn_ok and flaresolverr_ok:
                self._step("prowlarr", self.configure_prowlarr, True)
            else:
                self.runtime.set("prowlarr", "waiting", "Waiting for Privado and FlareSolverr")
            if vpn_ok:
                self._step("bazarr", self.configure_bazarr, True)
            else:
                self.runtime.set("bazarr", "waiting", "Waiting for a healthy Privado tunnel")
            self._step("profilarr", self.configure_profilarr)
            self._step("overseerr", self.configure_overseerr)
            self.runtime.event("Reconciliation completed")
        finally:
            self.runtime.complete()

    def _mark_setup_required(self):
        self.runtime.set("umbrelarr", "action_required", "Detect and connect the Umbrel Arr apps you installed")
        for slug in REQUIRED_APPS:
            self.runtime.set(slug, "unknown", "Waiting for explicit Umbrelarr setup")

    def ensure_setup(self):
        with self._setup_lock:
            if self._setup_complete:
                return True
        key = self.settings.key("prowlarr")
        url = self.settings.url("prowlarr")
        if not key or not url:
            return False
        try:
            tags = self.client.json("GET", f"{url}/api/v1/tag", key)
        except (RequestError, OSError, ValueError):
            return False
        complete = any(
            item.get("label", "").casefold() == SETUP_MARKER_TAG
            for item in tags or []
        )
        with self._setup_lock:
            self._setup_complete = complete
        return complete

    def setup_snapshot(self):
        confirmed = self.ensure_setup()
        ready = self.ensure_setup_ready()
        with self._setup_lock:
            apps = [dict(item) for item in self._setup_detection]
        reachable = sum(item["reachable"] for item in apps)
        detection_complete = len(apps) == len(REQUIRED_APPS)
        blocking = [
            item for item in apps
            if not item["reachable"] or (not item["credentials"] and item["id"] != "qbittorrent")
        ]
        can_confirm = detection_complete and not blocking
        if ready:
            phase = "confirmed"
        elif confirmed:
            phase = "action_required"
        elif not detection_complete:
            phase = "detect"
        elif can_confirm:
            phase = "ready"
        else:
            phase = "action_required"
        return {
            "phase": phase,
            "confirmed": confirmed,
            "canConfirm": can_confirm,
            "requiredCount": len(REQUIRED_APPS),
            "detectedCount": reachable,
            "detectionComplete": detection_complete,
            "apps": apps,
        }

    def ensure_setup_ready(self):
        if not self.ensure_setup():
            return False
        with self._setup_lock:
            if self._setup_ready:
                return True
        ready = any(
            item.get("label", "").casefold() == SETUP_READY_MARKER_TAG
            for item in self._prowlarr_tags(required=False)
        )
        with self._setup_lock:
            self._setup_ready = ready
        return ready

    def detect_apps(self):
        with ThreadPoolExecutor(max_workers=min(8, len(REQUIRED_APPS))) as executor:
            apps = list(executor.map(self._detect_app, REQUIRED_APPS))
        with self._setup_lock:
            self._setup_detection = apps
        self.runtime.event(f"Detected {sum(item['reachable'] for item in apps)} of {len(apps)} installed Umbrel Arr apps")
        return self.setup_snapshot()

    def _detect_app(self, slug):
        url = self.settings.url(slug)
        reachable = False
        probe_succeeded = False
        detail = "No configured service address"
        if url:
            try:
                probe = f"{url}/api/v2/app/version" if slug == "qbittorrent" else f"{url}/"
                self.client.request("GET", probe, timeout=3)
                reachable = True
                probe_succeeded = True
                detail = "Installed app is reachable"
            except RequestError as error:
                if error.status is not None:
                    reachable = True
                    detail = "Installed app is reachable"
                else:
                    detail = "App was not reachable"
        if slug == "qbittorrent":
            credentials = probe_succeeded
            # A successful version probe means legacy unauthenticated access.
            # Authentication errors are reachable but require the temporary
            # password to be supplied only to the confirmation request.
            if reachable and not credentials:
                detail = "Enter qBittorrent's one-time password when confirming setup"
        else:
            credentials = slug not in KEYED_APPS or bool(self.settings.key(slug))
        if reachable and not credentials and slug != "qbittorrent":
            detail = "Installed app found; waiting for its API key"
        action = "none"
        if not reachable:
            action = "install_or_start"
        elif not credentials:
            action = "temporary_password_required" if slug == "qbittorrent" else "wait_for_api_key"
        return {
            "id": slug,
            "name": NAMES[slug],
            "reachable": reachable,
            "credentials": credentials,
            "action": action,
            "detected": reachable,
            "detail": detail,
            "link": self.settings.external_url(slug),
        }

    def confirm_setup(
        self, storage_mode="", root_ids=None,
        qbittorrent_username="admin", qbittorrent_temporary_password="",
    ):
        snapshot = self.setup_snapshot()
        if not snapshot["detectionComplete"]:
            raise ValueError("Detect installed apps before connecting them")
        missing = [item["name"] for item in snapshot["apps"] if not item["reachable"]]
        if missing:
            raise ValueError(f"Install or start these required apps first: {', '.join(missing)}")
        missing_keys = [
            item["name"] for item in snapshot["apps"]
            if item["id"] != "qbittorrent" and not item["credentials"]
        ]
        if missing_keys:
            raise ValueError(f"Wait for these apps to generate API credentials: {', '.join(missing_keys)}")
        if not storage_mode:
            raise ValueError("Choose local, network, or existing library roots before confirming setup")
        self._validate_storage_selection(storage_mode, root_ids or {})
        key = self.settings.key("prowlarr")
        api = f"{self.settings.url('prowlarr')}/api/v1"
        tags = self.client.json("GET", f"{api}/tag", key)
        marker = next(
            (item for item in tags if item.get("label", "").casefold() == SETUP_MARKER_TAG),
            None,
        )
        if marker is None:
            self.client.json("POST", f"{api}/tag", key, {"label": SETUP_MARKER_TAG})
        with self._setup_lock:
            self._setup_complete = True
        self._onboard_qbittorrent(qbittorrent_username, qbittorrent_temporary_password)
        self._apply_storage(storage_mode, root_ids or {})
        tags = self.client.json("GET", f"{api}/tag", key)
        if not any(item.get("label", "").casefold() == SETUP_READY_MARKER_TAG for item in tags):
            self.client.json("POST", f"{api}/tag", key, {"label": SETUP_READY_MARKER_TAG})
        with self._setup_lock:
            self._setup_ready = True
        self.runtime.event("Explicit setup completed; installed apps are now managed")
        self.reconcile_async()
        return self.setup_snapshot()

    def _step(self, slug, callback, *args):
        self.runtime.set(slug, "configuring", "Checking managed configuration")
        try:
            detail = callback(*args)
            if isinstance(detail, tuple):
                status, message = detail
                self.runtime.set(slug, status, message)
                return status == "healthy"
            self.runtime.set(slug, "healthy", detail or "Managed configuration is current")
            return True
        except RequestError as error:
            status = "waiting" if error.status in {502, 503, 504} or error.status is None else "failed"
            self.runtime.set(slug, status, self._safe_error(error))
            self.runtime.event(f"{NAMES[slug]}: {self._safe_error(error)}", "error")
            return False
        except (KeyError, ValueError, RuntimeError, OSError) as error:
            self.runtime.set(slug, "failed", self._safe_error(error))
            self.runtime.event(f"{NAMES[slug]}: {self._safe_error(error)}", "error")
            return False

    @staticmethod
    def _safe_error(error):
        value = str(error)
        value = re.sub(
            r"(?i)(api[_-]?key|password|token)(?:[\"']?\s*[:=]\s*[\"']?)([^&\s,}\"']+)",
            r"\1=[redacted]", value,
        )
        return value[:300]

    def configure_storage(self):
        snapshot = self.storage_snapshot()
        if snapshot["actionRequired"]:
            return "action_required", "Choose one existing root folder for each library"
        return "Library roots were derived from the managed Arr APIs"

    def storage_snapshot(self):
        folders = self._read_root_folders(required=False)
        mode, root_ids = self._storage_marker_selection(self._prowlarr_tags(required=False))
        return self.storage.update_from_apis(folders, mode, root_ids)

    def save_storage(self, mode, root_ids):
        if not self.ensure_setup_ready():
            raise RuntimeError("Complete explicit setup before changing library roots")
        snapshot = self._apply_storage(mode, root_ids)
        self.runtime.event(f"Library layout applied through service APIs for {mode} storage")
        self.reconcile_async()
        return snapshot

    def _apply_storage(self, mode, root_ids):
        if mode == "adopt":
            mode = "adopted"
        if mode not in {*PRESETS, "adopted"}:
            raise ValueError("Storage mode must be local, network, or adopt")
        folders = self._read_root_folders(required=True)
        if mode in PRESETS:
            self.storage.update_from_apis(folders, mode)
            self.arrs = self._arr_instances()
            for arr in self.arrs:
                self._ensure_root(arr)
            folders = self._read_root_folders(required=True)
            snapshot = self.storage.update_from_apis(folders, mode)
            if set(snapshot["rootIds"]) != set(LOCAL_ROOTS):
                raise RuntimeError("The selected preset roots were not accepted by every Arr app")
            marker_labels = [f"{STORAGE_MARKER_PREFIX}{mode}"]
        else:
            cleaned_ids = {
                slug: int(value) for slug, value in root_ids.items()
                if slug in LOCAL_ROOTS and str(value).strip()
            }
            snapshot = self.storage.update_from_apis(folders, "adopted", cleaned_ids)
            if snapshot["actionRequired"]:
                raise ValueError("Choose one existing root-folder ID for every library")
            marker_labels = [
                f"{STORAGE_MARKER_PREFIX}{slug}-{snapshot['rootIds'][slug]}"
                for slug in LOCAL_ROOTS
            ]
        self._replace_storage_markers(marker_labels)
        self.arrs = self._arr_instances()
        return snapshot

    def _validate_storage_selection(self, mode, root_ids):
        normalized = "adopted" if mode == "adopt" else mode
        if normalized not in {*PRESETS, "adopted"}:
            raise ValueError("Storage mode must be local, network, or adopt")
        if normalized != "adopted":
            return
        folders = self._read_root_folders(required=True)
        cleaned_ids = {
            slug: int(value) for slug, value in root_ids.items()
            if slug in LOCAL_ROOTS and str(value).strip()
        }
        candidate = StorageSettings().update_from_apis(folders, "adopted", cleaned_ids)
        if candidate["actionRequired"]:
            raise ValueError("Choose one existing root-folder ID for every library")

    def _read_root_folders(self, required):
        folders = {}
        for arr in self._arr_instances():
            if not arr.url or not arr.api_key:
                if required:
                    raise ValueError(f"{arr.name} API credentials are not available")
                folders[arr.slug] = []
                continue
            try:
                values = self.client.json("GET", f"{arr.api}/rootfolder", arr.api_key)
            except (RequestError, OSError, ValueError):
                if required:
                    raise
                values = []
            folders[arr.slug] = values if isinstance(values, list) else []
        return folders

    def _prowlarr_tags(self, required=True):
        key = self.settings.key("prowlarr")
        url = self.settings.url("prowlarr")
        if not key or not url:
            if required:
                raise ValueError("Prowlarr API credentials are not available")
            return []
        try:
            values = self.client.json("GET", f"{url}/api/v1/tag", key)
        except (RequestError, OSError, ValueError):
            if required:
                raise
            return []
        return values if isinstance(values, list) else []

    @staticmethod
    def _storage_marker_selection(tags):
        labels = {
            str(item.get("label", "")).casefold()
            for item in tags
        }
        for mode in PRESETS:
            if f"{STORAGE_MARKER_PREFIX}{mode}" in labels:
                return mode, {}
        root_ids = {}
        for slug in LOCAL_ROOTS:
            prefix = f"{STORAGE_MARKER_PREFIX}{slug}-"
            label = next(
                (value for value in labels if re.fullmatch(rf"{re.escape(prefix)}\d+", value)),
                "",
            )
            try:
                root_ids[slug] = int(label.removeprefix(prefix))
            except ValueError:
                pass
        return ("adopted", root_ids) if root_ids else (None, {})

    def _replace_storage_markers(self, labels):
        key = self.settings.key("prowlarr")
        api = f"{self.settings.url('prowlarr')}/api/v1"
        tags = self._prowlarr_tags()
        existing = {
            str(item.get("label", "")).casefold(): item
            for item in tags
        }
        desired = {label.casefold() for label in labels}
        for label, item in existing.items():
            if label.startswith(STORAGE_MARKER_PREFIX) and label not in desired:
                self.client.json("DELETE", f"{api}/tag/{item['id']}", key)
        for label in labels:
            if label.casefold() not in existing:
                self.client.json("POST", f"{api}/tag", key, {"label": label})

    def _onboard_qbittorrent(self, username="admin", temporary_password=""):
        base = f"{self.settings.url('qbittorrent')}/api/v2"
        deterministic = self.settings.qbittorrent_password
        try:
            self.client.request("GET", f"{base}/app/version", timeout=5)
            self._qbittorrent_cookie = ""
        except RequestError as error:
            if error.status not in {401, 403}:
                raise
            authenticated = False
            if deterministic:
                authenticated = self._qbit_login("admin", deterministic)
            if not authenticated and temporary_password:
                authenticated = self._qbit_login(username.strip() or "admin", temporary_password)
            if not authenticated:
                raise ValueError("Enter qBittorrent's one-time admin password to continue")
        if not deterministic:
            raise ValueError("The deterministic qBittorrent password export is missing")
        current = self.client.json(
            "GET", f"{base}/app/preferences", headers=self._qbit_headers(),
        ) or {}
        web_preferences = self._qbit_security_preferences(current)
        web_preferences.update({"web_ui_username": "admin", "web_ui_password": deterministic})
        self.client.form(
            "POST",
            f"{base}/app/setPreferences",
            {"json": json.dumps(web_preferences)},
            self._qbit_headers(),
        )
        if not self._qbittorrent_cookie:
            if not self._qbit_login("admin", deterministic):
                raise RuntimeError("qBittorrent did not accept its configured Umbrel password")

    def _qbit_login(self, username, password):
        origin = self.settings.url("qbittorrent")
        try:
            response = self.client.form(
                "POST",
                f"{origin}/api/v2/auth/login",
                {"username": username, "password": password},
                {"Origin": origin, "Referer": f"{origin}/"},
            )
        except RequestError as error:
            if error.status in {401, 403}:
                return False
            raise
        body = response.body.decode("utf-8", "replace").strip()
        if body and body.casefold().startswith("fails"):
            return False
        cookie = response.headers.get("Set-Cookie", "") if response.headers else ""
        self._qbittorrent_cookie = cookie.split(";", 1)[0]
        cookie_name, separator, _value = self._qbittorrent_cookie.partition("=")
        return bool(separator) and (
            cookie_name == "SID" or cookie_name.startswith("QBT_SID_")
        )

    def _qbit_headers(self):
        origin = self.settings.url("qbittorrent")
        headers = {"Origin": origin, "Referer": f"{origin}/"}
        if self._qbittorrent_cookie:
            headers["Cookie"] = self._qbittorrent_cookie
        return headers

    def _qbit_security_preferences(self, current):
        domains = {
            value.strip() for value in str(current.get("web_ui_domain_list", "")).split(";")
            if value.strip() and value.strip() != "*"
        }
        internal_host = urlsplit(self.settings.url("qbittorrent")).hostname
        domains.update(value for value in (internal_host, self.settings.device_domain, "localhost") if value)
        return {
            "web_ui_csrf_protection_enabled": True,
            "web_ui_clickjacking_protection_enabled": True,
            "web_ui_host_header_validation_enabled": True,
            "web_ui_domain_list": ";".join(sorted(domains)),
            "web_ui_secure_cookie_enabled": False,
            "web_ui_upnp": False,
            "bypass_local_auth": False,
            "bypass_auth_subnet_whitelist_enabled": False,
            "bypass_auth_subnet_whitelist": "",
        }

    def check_vpn(self):
        status = self.client.json("GET", f"{self.settings.url('privado-vpn')}/api/status")
        if status.get("state") == "healthy":
            public_ip = status.get("publicIp") or "private exit"
            return f"WireGuard and SOCKS5 are healthy via {public_ip}"
        if not status.get("credentialsConfigured"):
            return "action_required", "Enter your Privado login to start the tunnel"
        return "waiting", f"Privado is {status.get('state', 'starting')}; waiting for WireGuard and SOCKS5"

    def save_vpn_login(self, username, password):
        if not username.strip() or not password:
            raise ValueError("Privado username and password are required")
        self.client.form(
            "POST",
            f"{self.settings.url('privado-vpn')}/setup",
            {"username": username.strip(), "password": password},
        )
        self.runtime.event("Privado login forwarded to the VPN app")
        self.reconcile_async()

    def check_flaresolverr(self):
        response = self.client.json("POST", f"{self.settings.url('flaresolverr')}/v1", payload={"cmd": "sessions.list", "maxTimeout": 10000})
        if response.get("status") != "ok":
            raise RuntimeError("FlareSolverr did not return a healthy response")
        return "Challenge solver is reachable through the Privado proxy"

    def configure_qbittorrent(self, vpn_ok):
        base = f"{self.settings.url('qbittorrent')}/api/v2"
        try:
            self.client.request("GET", f"{base}/app/version", headers=self._qbit_headers())
        except RequestError as error:
            if error.status not in {401, 403} or not self.settings.qbittorrent_password:
                if error.status in {401, 403}:
                    return "action_required", "Complete qBittorrent authentication in explicit setup"
                raise
            if not self._qbit_login("admin", self.settings.qbittorrent_password):
                return "action_required", "qBittorrent rejected its configured Umbrel password"
        if not vpn_ok:
            return "waiting", "Waiting for a healthy Privado tunnel before applying proxy settings"
        current = self.client.json(
            "GET", f"{base}/app/preferences", headers=self._qbit_headers(),
        ) or {}
        preferences = {
            **self._qbit_security_preferences(current),
            "proxy_type": "SOCKS5",
            "proxy_ip": self.settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_HOST", "umbrel-arr-privado-vpn_server_1"),
            "proxy_port": int(self.settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_PORT", "1080")),
            "proxy_peer_connections": True,
            "proxy_hostname_lookup": True,
            "proxy_bittorrent": True,
            "proxy_misc": True,
            "proxy_rss": True,
            "proxy_torrents_only": False,
            "save_path": "/downloads/complete/",
            "temp_path": "/downloads/incomplete/",
            "temp_path_enabled": True,
        }
        self.client.form(
            "POST", f"{base}/app/setPreferences",
            {"json": json.dumps(preferences)}, self._qbit_headers(),
        )
        for category in ("movies", "movies-4k", "tv", "tv-4k", "music"):
            try:
                self.client.form(
                    "POST", f"{base}/torrents/createCategory",
                    {"category": category, "savePath": f"/downloads/complete/{category}"},
                    self._qbit_headers(),
                )
            except RequestError as error:
                if error.status != 409:
                    raise
        return "Privado SOCKS5, shared paths, and five media categories are configured"

    def configure_sabnzbd(self, vpn_ok):
        url = self.settings.url("sabnzbd")
        key = self.settings.key("sabnzbd")
        if not key:
            return "waiting", "Waiting for SABnzbd to persist its API key"
        self._sab_call(url, key, {"mode": "version"})
        if not vpn_ok:
            return "waiting", "Waiting for a healthy Privado tunnel before applying proxy settings"
        for keyword, value in {
            "socks5_proxy_url": f"socks5://{self.settings.env.get('UMBREL_ARR_PRIVADO_SOCKS_HOST', 'umbrel-arr-privado-vpn_server_1')}:{self.settings.env.get('UMBREL_ARR_PRIVADO_SOCKS_PORT', '1080')}",
            "complete_dir": "/downloads/complete",
            "download_dir": "/downloads/incomplete",
            "username": "",
            "password": "",
        }.items():
            self._sab_call(url, key, {"mode": "set_config", "section": "misc", "keyword": keyword, "value": value})
        for category in ("movies", "movies-4k", "tv", "tv-4k", "music"):
            self._sab_call(url, key, {"mode": "set_config", "section": "categories", "name": category, "dir": category})
        return "Privado SOCKS5, shared paths, and five media categories are configured"

    def _sab_call(self, url, key, values):
        query = {**values, "apikey": key, "output": "json"}
        parsed = urlsplit(url)
        trusted_host = "localhost" if parsed.port is None else f"localhost:{parsed.port}"
        response = self.client.form(
            "POST", f"{url}/api", query, {"Host": trusted_host},
        )
        if response.body:
            data = response.json()
            if isinstance(data, dict) and data.get("status") is False:
                raise RuntimeError(f"SABnzbd rejected {values.get('mode')}")
        return response

    def configure_arr(self, arr):
        if not arr.api_key:
            return "waiting", f"Waiting for {arr.name} to persist its API key"
        self.client.json("GET", f"{arr.api}/system/status", arr.api_key)
        self._ensure_root(arr)
        self._ensure_download_client(arr, "QBittorrent", "Umbrel Arr qBittorrent", self.settings.url("qbittorrent"))
        self._ensure_download_client(arr, "Sabnzbd", "Umbrel Arr SABnzbd", self.settings.url("sabnzbd"), self.settings.key("sabnzbd"))
        return f"Root {arr.root} and both {arr.category} download clients are configured"

    def _ensure_root(self, arr):
        existing = self.client.json("GET", f"{arr.api}/rootfolder", arr.api_key)
        if not any(item.get("path", "").rstrip("/") == arr.root.rstrip("/") for item in existing):
            payload = {"path": arr.root}
            if arr.implementation == "Lidarr":
                metadata_profiles = self.client.json("GET", f"{arr.api}/metadataprofile", arr.api_key)
                quality_profiles = self.client.json("GET", f"{arr.api}/qualityprofile", arr.api_key)
                if not metadata_profiles or not quality_profiles:
                    raise RuntimeError("Lidarr has no metadata or quality profile for the music root")
                metadata = next(
                    (item for item in metadata_profiles if item.get("name") == "Standard"),
                    metadata_profiles[0],
                )
                quality = next(
                    (item for item in quality_profiles if item.get("name") == "Any"),
                    quality_profiles[0],
                )
                payload["name"] = Path(arr.root).name.replace("-", " ").title() or "Music"
                payload["defaultMetadataProfileId"] = metadata["id"]
                payload["defaultQualityProfileId"] = quality["id"]
            self.client.json("POST", f"{arr.api}/rootfolder", arr.api_key, payload)

    def _ensure_download_client(self, arr, implementation, name, client_url, client_key=None):
        schemas = self.client.json("GET", f"{arr.api}/downloadclient/schema", arr.api_key)
        existing = self.client.json("GET", f"{arr.api}/downloadclient", arr.api_key)
        payload = self._schema(schemas, implementation)
        target = urlsplit(client_url)
        values = {
            "host": target.hostname,
            "port": target.port,
            "useSsl": target.scheme == "https",
            "urlBase": target.path.rstrip("/"),
            "category": arr.category,
        }
        if client_key:
            values["apiKey"] = client_key
        self._set_fields(payload, values)
        payload.update({"name": name, "enable": True, "priority": 1, "removeCompletedDownloads": True, "removeFailedDownloads": True, "tags": []})
        self._upsert(arr.api, "downloadclient", arr.api_key, payload, existing)

    def configure_prowlarr(self, vpn_ok):
        url = self.settings.url("prowlarr")
        key = self.settings.key("prowlarr")
        if not key:
            return "waiting", "Waiting for Prowlarr to persist its API key"
        api = f"{url}/api/v1"
        self.client.json("GET", f"{api}/system/status", key)
        if vpn_ok:
            config = self.client.json("GET", f"{api}/config/host", key)
            config.update({
                "proxyEnabled": True,
                "proxyType": "socks5",
                "proxyHostname": self.settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_HOST", "umbrel-arr-privado-vpn_server_1"),
                "proxyPort": int(self.settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_PORT", "1080")),
                "proxyBypassFilter": ",".join(f"umbrel-arr-{slug}_server_1" for slug in NAMES),
                "proxyBypassLocalAddresses": True,
            })
            self.client.json("PUT", f"{api}/config/host/{config.get('id', 1)}", key, config)
        self._configure_flaresolverr_proxy(api, key)
        schemas = self.client.json("GET", f"{api}/applications/schema", key)
        existing = self.client.json("GET", f"{api}/applications", key)
        for arr in self.arrs:
            payload = self._schema(schemas, arr.implementation)
            self._set_fields(payload, {"prowlarrUrl": url, "baseUrl": arr.url, "apiKey": arr.api_key})
            payload.update({"name": f"Umbrel Arr {arr.name}", "syncLevel": "fullSync", "tags": []})
            self._upsert(api, "applications", key, payload, existing)
        vpn_note = "VPN proxy and " if vpn_ok else ""
        return f"{vpn_note}FlareSolverr plus five full-sync Arr applications are configured"

    def _configure_flaresolverr_proxy(self, api, key):
        tags = self.client.json("GET", f"{api}/tag", key)
        tag = next((item for item in tags if item.get("label", "").casefold() == "flaresolverr"), None)
        if tag is None:
            tag = self.client.json("POST", f"{api}/tag", key, {"label": "flaresolverr"})
        schemas = self.client.json("GET", f"{api}/indexerproxy/schema", key)
        existing = self.client.json("GET", f"{api}/indexerproxy", key)
        payload = self._schema(schemas, "FlareSolverr")
        self._set_fields(payload, {"host": self.settings.url("flaresolverr"), "requestTimeout": 60})
        payload.update({"name": "Umbrel Arr FlareSolverr", "tags": [tag["id"]]})
        self._upsert(api, "indexerproxy", key, payload, existing)

    def configure_bazarr(self, vpn_ok):
        key = self.settings.key("bazarr")
        if not key:
            return "waiting", "Waiting for Bazarr to persist its API key"
        values = {
            "settings-general-use_sonarr": "true",
            "settings-sonarr-ip": urlsplit(self.settings.url("sonarr")).hostname,
            "settings-sonarr-port": "8989",
            "settings-sonarr-base_url": "/",
            "settings-sonarr-ssl": "false",
            "settings-sonarr-apikey": self.settings.key("sonarr"),
            "settings-general-use_radarr": "true",
            "settings-radarr-ip": urlsplit(self.settings.url("radarr")).hostname,
            "settings-radarr-port": "7878",
            "settings-radarr-base_url": "/",
            "settings-radarr-ssl": "false",
            "settings-radarr-apikey": self.settings.key("radarr"),
        }
        if vpn_ok:
            values.update({
                "settings-proxy-type": "socks5",
                "settings-proxy-url": self.settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_HOST", "umbrel-arr-privado-vpn_server_1"),
                "settings-proxy-port": self.settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_PORT", "1080"),
                "settings-proxy-exclude": ["localhost", "127.0.0.1", urlsplit(self.settings.url("sonarr")).hostname, urlsplit(self.settings.url("radarr")).hostname],
            })
        self.client.form("POST", f"{self.settings.url('bazarr')}/api/system/settings", values, {"X-API-KEY": key})
        return "HD Sonarr and Radarr are connected" + (" through Privado" if vpn_ok else "")

    def configure_profilarr(self):
        url = self.settings.url("profilarr")
        form_headers = {"Origin": url, "Referer": f"{url}/"}
        self.client.json("GET", f"{url}/api/v1/status")
        databases = self.client.json("GET", f"{url}/api/v1/databases")
        database = next((item for item in databases if item.get("repository_url") == DATABASE_URL or item.get("name") == "Dictionarry"), None)
        if database is None:
            self.client.form("POST", f"{url}/databases/new", {"name": "Dictionarry", "repository_url": DATABASE_URL, "branch": "v2", "sync_strategy": "1440", "auto_pull": "1"}, form_headers)
            return "waiting", "Dictionarry database link queued; waiting for Profilarr to index it"
        instances = self.client.json("GET", f"{url}/api/v1/arr")
        current = {item.get("name"): item for item in instances}
        for arr in self.arrs[:4]:
            if arr.name not in current:
                self.client.form("POST", f"{url}/arr/new", {"name": arr.name, "type": arr.implementation.lower(), "url": arr.url, "external_url": self.settings.external_url(arr.slug), "api_key": arr.api_key, "tags": json.dumps(["4k" if arr.is_4k else "hd", MANAGED_TAG])}, form_headers)
        instances = self.client.json("GET", f"{url}/api/v1/arr")
        current = {item.get("name"): item for item in instances}
        missing = [arr.name for arr in self.arrs[:4] if arr.name not in current]
        if missing:
            return "waiting", f"Waiting for Profilarr Arr connections: {', '.join(missing)}"
        sync_marker_present = any(
            str(item.get("label", "")).casefold() == PROFILARR_SYNC_MARKER_TAG
            for item in self._prowlarr_tags()
        )
        for arr in self.arrs[:4]:
            profiles = UHD_PROFILES if arr.is_4k else HD_PROFILES
            selections = [{"databaseId": database["id"], "profileName": name} for name in profiles]
            instance_id = current[arr.name]["id"]
            self.client.form("POST", f"{url}/arr/{instance_id}/sync?/saveQualityProfiles", {"selections": json.dumps(selections), "priorities": json.dumps([{"databaseId": database["id"], "priority": 1}]), "trigger": "schedule", "cron": "0 3 * * *"}, {**form_headers, "x-sveltekit-action": "true"})
            if not sync_marker_present:
                try:
                    self.client.form("POST", f"{url}/arr/{instance_id}/sync?/syncQualityProfiles", {}, {**form_headers, "x-sveltekit-action": "true"})
                except RequestError as error:
                    if error.status != 409:
                        raise
        if not sync_marker_present:
            prowlarr_key = self.settings.key("prowlarr")
            self.client.json(
                "POST", f"{self.settings.url('prowlarr')}/api/v1/tag",
                prowlarr_key, {"label": PROFILARR_SYNC_MARKER_TAG},
            )
        return "Dictionarry profiles and referenced custom formats sync daily to four Arr instances"

    def configure_overseerr(self):
        url = self.settings.url("overseerr")
        key = self.settings.key("overseerr")
        public = self.client.json("GET", f"{url}/api/v1/settings/public")
        if not public.get("initialized"):
            return "action_required", "Complete the Plex sign-in in Overseerr; server registration will continue automatically"
        if not key:
            return "waiting", "Waiting for Overseerr to persist its API key"
        headers = {"X-API-Key": key}
        for kind, arrs in (("sonarr", self.arrs[:2]), ("radarr", self.arrs[2:4])):
            existing = self.client.json("GET", f"{url}/api/v1/settings/{kind}", headers=headers)
            for arr in arrs:
                target = urlsplit(arr.url)
                discovered = self.client.json("POST", f"{url}/api/v1/settings/{kind}/test", payload={"hostname": target.hostname, "port": target.port, "apiKey": arr.api_key, "baseUrl": "", "useSsl": False}, headers=headers)
                root = next((item for item in discovered.get("rootFolders", []) if item.get("path", "").rstrip("/") == arr.root.rstrip("/")), None)
                if root is None:
                    raise RuntimeError(f"{arr.name} root {arr.root} is not available yet")
                profile = self._overseerr_profile(discovered.get("profiles", []), arr.is_4k)
                payload = {"hostname": target.hostname, "port": target.port, "apiKey": arr.api_key, "baseUrl": "", "useSsl": False, "name": f"Umbrel Arr {arr.name}", "activeProfileId": profile["id"], "activeProfileName": profile["name"], "activeDirectory": root["path"], "tags": [], "is4k": arr.is_4k, "isDefault": not arr.is_4k, "externalUrl": self.settings.external_url(arr.slug), "syncEnabled": True, "preventSearch": False, "tagRequests": False}
                if kind == "sonarr":
                    payload.update({"seriesType": "standard", "animeSeriesType": "anime", "animeTags": [], "enableSeasonFolders": True})
                    languages = discovered.get("languageProfiles", [])
                    if languages:
                        payload["activeLanguageProfileId"] = languages[0]["id"]
                else:
                    payload["minimumAvailability"] = "released"
                match = next((item for item in existing if item.get("name") == payload["name"]), None)
                method = "PUT" if match else "POST"
                endpoint = f"{url}/api/v1/settings/{kind}" + (f"/{match['id']}" if match else "")
                self.client.json(method, endpoint, payload=payload, headers=headers)
        return "HD defaults and separate 4K Sonarr and Radarr servers are registered"

    @staticmethod
    def _overseerr_profile(profiles, is_4k):
        preferences = ["2160p Quality", "2160p Efficient"] if is_4k else ["1080p Quality HDR", "1080p Efficient", "1080p Compact"]
        for name in preferences:
            match = next((profile for profile in profiles if profile.get("name") == name), None)
            if match:
                return match
        if profiles:
            return profiles[0]
        raise RuntimeError("No quality profiles are available yet")

    @staticmethod
    def _schema(schemas, implementation):
        try:
            return copy.deepcopy(next(item for item in schemas if item.get("implementation", "").casefold() == implementation.casefold()))
        except StopIteration as error:
            raise RuntimeError(f"No provider schema for {implementation}") from error

    @staticmethod
    def _set_fields(provider, values):
        fields = {field.get("name", "").casefold(): field for field in provider.get("fields", [])}
        for name, value in values.items():
            if name.casefold() in fields:
                fields[name.casefold()]["value"] = value

    def _upsert(self, base, route, key, payload, existing):
        match = next((item for item in existing if item.get("name") == payload.get("name")), None)
        if match:
            payload["id"] = match["id"]
            return self.client.json("PUT", f"{base}/{route}/{match['id']}", key, payload)
        payload.pop("id", None)
        created = self.client.json("POST", f"{base}/{route}", key, payload)
        if isinstance(created, dict):
            existing.append(created)
        return created


class ReconcileLoop:
    def __init__(self, reconciler):
        self.reconciler = reconciler
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            if self.reconciler.ensure_setup_ready():
                self.reconciler.reconcile()
            else:
                self.reconciler._mark_setup_required()
            self.stop_event.wait(self.reconciler.settings.interval)
