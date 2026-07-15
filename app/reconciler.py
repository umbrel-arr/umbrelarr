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
from catalog import (
    DEFAULT_MODULES, MEDIA_MODULES, MODULES, SERVICE_MODULES, STACK_PROFILES, VIDEO_MODULES,
    dependencies_for, normalize_modules, validate_modules,
)
from http_client import HttpClient, RequestError
from state import RuntimeState, ServiceStatus
from storage import LOCAL_ROOTS, PRESETS, StorageSettings
from vpn import VPN_PROVIDERS, get_vpn_provider


MANAGED_TAG = "umbrel-arr-managed"
SETUP_MARKER_TAG = "umbrel-arr-setup-complete"
SETUP_READY_MARKER_TAG = "umbrel-arr-setup-ready-v1"
PROFILARR_SYNC_MARKER_TAG = "umbrel-arr-profilarr-initial-sync-v1"
STORAGE_MARKER_PREFIX = "umbrel-arr-storage-"
MODULE_CATALOG_MARKER_TAG = "umbrel-arr-modular-selection-v1"
MODULE_MARKER_PREFIX = "umbrel-arr-module-"
VPN_PROVIDER_MARKER_PREFIX = "umbrel-arr-vpn-provider-"
DATABASE_URL = "https://github.com/Dictionarry-Hub/database"
HD_PROFILES = ["1080p Compact", "1080p Efficient", "1080p Quality HDR"]
UHD_PROFILES = ["2160p Efficient", "2160p Quality"]


APP_PORTS = {module.id: module.port for module in SERVICE_MODULES}
NAMES = {module.id: module.name for module in SERVICE_MODULES}
MEDIA_APPS = MEDIA_MODULES
HD_UHD_VIDEO_APPS = VIDEO_MODULES
# Compatibility exports describe the default 1.1 stack. Runtime requirements
# are derived from the user's selected modules instead.
REQUIRED_APPS = tuple(slug for slug in NAMES if slug != "umbrelarr")
KEYED_APPS = {module.id for module in SERVICE_MODULES if module.requires_api_key}
DEPENDENCIES = dependencies_for(DEFAULT_MODULES, "privado-vpn")


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
        configured_modules = env.get("UMBREL_ARR_ENABLED_SERVICES", "")
        self.enabled_modules = normalize_modules(
            configured_modules.split(",") if configured_modules.strip() else DEFAULT_MODULES
        )
        self.vpn_provider_id = env.get("UMBREL_ARR_VPN_PROVIDER", "privado").strip() or "privado"

    def url(self, slug):
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_URL"
        return self.env.get(key, "").rstrip("/")

    def key(self, slug):
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_API_KEY"
        exported = self.env.get(key, "").strip()
        return exported or self.api_keys.resolve(slug)

    def external_url(self, slug):
        port = APP_PORTS.get(slug)
        return f"http://{self.device_domain}:{port}" if port else ""

    @property
    def qbittorrent_password(self):
        return self.env.get("UMBREL_ARR_QBITTORRENT_PASSWORD", "")

    @property
    def qbittorrent_legacy_password(self):
        return self.env.get("UMBREL_ARR_QBITTORRENT_LEGACY_PASSWORD", "")


class Reconciler:
    def __init__(self, settings=None, client=None):
        self.settings = settings or Settings()
        self.client = client or HttpClient()
        self.storage = StorageSettings()
        self._setup_lock = threading.RLock()
        self._setup_complete = False
        self._setup_ready = False
        self._selection_dirty = False
        self._setup_detection = []
        self._qbittorrent_cookie = ""
        self.enabled_modules = frozenset()
        self.vpn_provider = get_vpn_provider(self.settings.vpn_provider_id)
        self._set_modules(self.settings.enabled_modules, self.vpn_provider.id)
        self._mark_setup_required()

    def _set_modules(self, enabled, vpn_provider_id):
        provider = get_vpn_provider(vpn_provider_id)
        selected = set(normalize_modules(enabled))
        selected.discard("privado-vpn")
        if provider.service_id:
            selected.add(provider.service_id)
        self.enabled_modules = normalize_modules(selected)
        self.vpn_provider = provider
        self.storage.set_enabled_modules(self.enabled_modules)
        dependencies = dependencies_for(self.enabled_modules, provider.service_id)
        previous_events = list(getattr(getattr(self, "runtime", None), "events", []))
        services = [
            ServiceStatus(slug, NAMES[slug], link=self.settings.external_url(slug))
            for slug in NAMES if slug in self.enabled_modules
        ]
        self.runtime = RuntimeState(services, dependencies)
        self.runtime.events = previous_events
        self.arrs = [arr for arr in self._arr_instances() if arr.slug in self.enabled_modules]

    def _selected_apps(self):
        return tuple(slug for slug in NAMES if slug != "umbrelarr" and slug in self.enabled_modules)

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
        self.arrs = [arr for arr in self._arr_instances() if arr.slug in self.enabled_modules]
        self.runtime.event("Reconciliation started")
        try:
            storage_ok = self._step("umbrelarr", self.configure_storage)
            if self.vpn_provider.service_id in self.enabled_modules:
                vpn_ok = self._step(self.vpn_provider.service_id, self.check_vpn)
            else:
                try:
                    vpn_status, vpn_detail = self.vpn_provider.check(self.settings, self.client)
                except (RequestError, OSError, ValueError) as error:
                    vpn_status, vpn_detail = "waiting", self._safe_error(error)
                vpn_ok = vpn_status == "healthy"
                if not vpn_ok:
                    self.runtime.set("umbrelarr", vpn_status, vpn_detail)
            flaresolverr_ok = "flaresolverr" not in self.enabled_modules
            if "flaresolverr" in self.enabled_modules:
                if vpn_ok:
                    flaresolverr_ok = self._step("flaresolverr", self.check_flaresolverr)
                else:
                    self.runtime.set("flaresolverr", "waiting", f"Waiting for {self.vpn_provider.name}")
            download_results = {}
            if "qbittorrent" in self.enabled_modules:
                download_results["qbittorrent"] = self._step("qbittorrent", self.configure_qbittorrent, vpn_ok)
            if "sabnzbd" in self.enabled_modules:
                download_results["sabnzbd"] = self._step("sabnzbd", self.configure_sabnzbd, vpn_ok)
            downloads_ok = all(download_results.values())
            if storage_ok and downloads_ok:
                for arr in self.arrs:
                    self._step(arr.slug, self.configure_arr, arr)
            else:
                detail = "Waiting for library storage" if not storage_ok else "Waiting for selected download clients"
                for arr in self.arrs:
                    self.runtime.set(arr.slug, "waiting", detail)
            if vpn_ok and flaresolverr_ok:
                self._step("prowlarr", self.configure_prowlarr, vpn_ok)
            else:
                self.runtime.set("prowlarr", "waiting", f"Waiting for selected network modules ({self.vpn_provider.name})")
            if "bazarr" in self.enabled_modules:
                if vpn_ok:
                    self._step("bazarr", self.configure_bazarr, vpn_ok)
                else:
                    self.runtime.set("bazarr", "waiting", f"Waiting for {self.vpn_provider.name}")
            if "profilarr" in self.enabled_modules:
                self._step("profilarr", self.configure_profilarr)
            if "overseerr" in self.enabled_modules:
                self._step("overseerr", self.configure_overseerr)
            self.runtime.event("Reconciliation completed")
        finally:
            self.runtime.complete()

    def _mark_setup_required(self):
        self.runtime.set("umbrelarr", "action_required", "Detect and connect the Umbrel Arr apps you installed")
        for slug in self._selected_apps():
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
        if complete:
            self._restore_module_selection(tags)
        with self._setup_lock:
            self._setup_complete = complete
        return complete

    def setup_snapshot(self):
        confirmed = self.ensure_setup()
        ready = self.ensure_setup_ready()
        with self._setup_lock:
            apps = [dict(item) for item in self._setup_detection]
        reachable = sum(item["reachable"] for item in apps)
        selected_apps = self._selected_apps()
        detection_complete = len(apps) == len(selected_apps)
        blocking = [
            item for item in apps
            if not item["reachable"] or (not item["credentials"] and item["id"] != "qbittorrent")
        ]
        vpn_status = self._vpn_setup_status()
        can_confirm = detection_complete and not blocking and vpn_status["ready"]
        if ready and self._selection_dirty:
            phase = "ready" if can_confirm else "action_required"
        elif ready:
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
            "requiredCount": len(selected_apps),
            "selectedCount": len(selected_apps),
            "detectedCount": reachable,
            "detectionComplete": detection_complete,
            "apps": apps,
            "enabledServices": list(self.enabled_modules),
            "modules": [
                {**module.public(), "enabled": module.id in self.enabled_modules}
                for module in SERVICE_MODULES if module.id != "umbrelarr"
            ],
            "profiles": [profile.public() for profile in STACK_PROFILES],
            "vpnProvider": self.vpn_provider.id,
            "vpnProviders": [provider.public() for provider in VPN_PROVIDERS.values()],
            "vpnStatus": vpn_status,
            "configurationChanged": self._selection_dirty,
        }

    def _vpn_setup_status(self):
        if self.vpn_provider.service_id:
            return {
                "ready": True,
                "status": "managed_app",
                "detail": f"{self.vpn_provider.name} health and login are managed after connection",
            }
        try:
            status, detail = self.vpn_provider.check(self.settings, self.client)
        except (RequestError, OSError, ValueError) as error:
            status, detail = "waiting", self._safe_error(error)
        return {"ready": status == "healthy", "status": status, "detail": detail}

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

    def _restore_module_selection(self, tags):
        labels = {
            str(item.get("label", "")).casefold()
            for item in tags or []
        }
        if MODULE_CATALOG_MARKER_TAG not in labels:
            # Migration path for 1.1: absence of the modular marker means the
            # complete legacy stack remains selected with Privado.
            return
        selected = {
            label.removeprefix(MODULE_MARKER_PREFIX)
            for label in labels if label.startswith(MODULE_MARKER_PREFIX)
        }
        provider_id = next(
            (
                label.removeprefix(VPN_PROVIDER_MARKER_PREFIX)
                for label in labels if label.startswith(VPN_PROVIDER_MARKER_PREFIX)
            ),
            self.settings.vpn_provider_id,
        )
        try:
            self._set_modules(selected, provider_id)
            self._selection_dirty = False
        except ValueError:
            # Invalid or stale API markers never authorize a surprise module
            # change. Keep the environment/default selection visible instead.
            return

    def _replace_module_markers(self, enabled, provider_id):
        key = self.settings.key("prowlarr")
        api = f"{self.settings.url('prowlarr')}/api/v1"
        tags = self._prowlarr_tags()
        desired = {
            MODULE_CATALOG_MARKER_TAG,
            f"{VPN_PROVIDER_MARKER_PREFIX}{provider_id}",
            *(f"{MODULE_MARKER_PREFIX}{slug}" for slug in enabled),
        }
        existing = {
            str(item.get("label", "")).casefold(): item
            for item in tags
        }
        managed = lambda label: (
            label == MODULE_CATALOG_MARKER_TAG
            or label.startswith(MODULE_MARKER_PREFIX)
            or label.startswith(VPN_PROVIDER_MARKER_PREFIX)
        )
        for label, item in existing.items():
            if managed(label) and label not in desired:
                self.client.json("DELETE", f"{api}/tag/{item['id']}", key)
        for label in sorted(desired):
            if label not in existing:
                self.client.json("POST", f"{api}/tag", key, {"label": label})

    def detect_apps(self):
        selected_apps = self._selected_apps()
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(selected_apps)))) as executor:
            apps = list(executor.map(self._detect_app, selected_apps))
        with self._setup_lock:
            self._setup_detection = apps
        self.runtime.event(f"Detected {sum(item['reachable'] for item in apps)} of {len(apps)} installed Umbrel Arr apps")
        return self.setup_snapshot()

    def select_and_detect(self, enabled_services, vpn_provider):
        selected = normalize_modules(
            self.enabled_modules if enabled_services is None else enabled_services
        )
        provider = get_vpn_provider(vpn_provider or self.vpn_provider.id)
        selected = normalize_modules(
            (set(selected) - {"privado-vpn"}) | ({provider.service_id} if provider.service_id else set())
        )
        errors = validate_modules(selected)
        if errors:
            raise ValueError("; ".join(errors))
        was_ready = self.ensure_setup_ready()
        changed = selected != self.enabled_modules or provider.id != self.vpn_provider.id
        self._set_modules(selected, provider.id)
        self._selection_dirty = was_ready and changed
        self._setup_detection = []
        self._mark_setup_required()
        return self.detect_apps()

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
            detail = (
                "Installed app found; waiting for its API key. Restart umbrelarr "
                "if this app was installed after umbrelarr started"
            )
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
        enabled_services=None, vpn_provider="",
    ):
        selected = normalize_modules(
            self.enabled_modules if enabled_services is None else enabled_services
        )
        provider_id = vpn_provider or self.vpn_provider.id
        provider = get_vpn_provider(provider_id)
        selected = normalize_modules(
            (set(selected) - {"privado-vpn"}) | ({provider.service_id} if provider.service_id else set())
        )
        errors = validate_modules(selected)
        if errors:
            raise ValueError("; ".join(errors))
        if selected != self.enabled_modules or provider_id != self.vpn_provider.id:
            self._set_modules(selected, provider_id)
            self._setup_detection = []
            raise ValueError("Module selection changed; run detection again before connecting apps")
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
        if not snapshot["vpnStatus"]["ready"]:
            raise ValueError(snapshot["vpnStatus"]["detail"])
        if self.arrs and not storage_mode:
            raise ValueError("Choose local, network, or existing library roots before confirming setup")
        if self.arrs:
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
        self._replace_module_markers(selected, provider_id)
        if "qbittorrent" in self.enabled_modules:
            self._onboard_qbittorrent(qbittorrent_username, qbittorrent_temporary_password)
        if self.arrs:
            self._apply_storage(storage_mode, root_ids or {})
        tags = self.client.json("GET", f"{api}/tag", key)
        if not any(item.get("label", "").casefold() == SETUP_READY_MARKER_TAG for item in tags):
            self.client.json("POST", f"{api}/tag", key, {"label": SETUP_READY_MARKER_TAG})
        with self._setup_lock:
            self._setup_ready = True
            self._selection_dirty = False
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
            self.arrs = [arr for arr in self._arr_instances() if arr.slug in self.enabled_modules]
            for arr in self.arrs:
                self._ensure_root(arr)
            folders = self._read_root_folders(required=True)
            snapshot = self.storage.update_from_apis(folders, mode)
            if set(snapshot["rootIds"]) != {arr.slug for arr in self.arrs}:
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
                for slug in {arr.slug for arr in self.arrs}
            ]
        self._replace_storage_markers(marker_labels)
        self.arrs = [arr for arr in self._arr_instances() if arr.slug in self.enabled_modules]
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
        candidate_storage = StorageSettings()
        candidate_storage.set_enabled_modules(self.enabled_modules)
        candidate = candidate_storage.update_from_apis(folders, "adopted", cleaned_ids)
        if candidate["actionRequired"]:
            raise ValueError("Choose one existing root-folder ID for every library")

    def _read_root_folders(self, required):
        folders = {}
        for arr in self.arrs:
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
            candidates = (deterministic, self.settings.qbittorrent_legacy_password)
            for password in dict.fromkeys(candidate for candidate in candidates if candidate):
                if self._qbit_login("admin", password):
                    authenticated = True
                    break
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
        status, detail = self.vpn_provider.check(self.settings, self.client)
        return detail if status == "healthy" else (status, detail)

    def save_vpn_login(self, username, password):
        self.vpn_provider.save_login(self.settings, self.client, username, password)
        self.runtime.event(f"{self.vpn_provider.name} login forwarded to the provider app")
        self.reconcile_async()

    def check_flaresolverr(self):
        response = self.client.json("POST", f"{self.settings.url('flaresolverr')}/v1", payload={"cmd": "sessions.list", "maxTimeout": 10000})
        if response.get("status") != "ok":
            raise RuntimeError("FlareSolverr did not return a healthy response")
        return f"Challenge solver is reachable through {self.vpn_provider.name} routing"

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
            return "waiting", f"Waiting for {self.vpn_provider.name} before applying network settings"
        current = self.client.json(
            "GET", f"{base}/app/preferences", headers=self._qbit_headers(),
        ) or {}
        preferences = {
            **self._qbit_security_preferences(current),
            "save_path": "/downloads/complete/",
            "temp_path": "/downloads/incomplete/",
            "temp_path_enabled": True,
        }
        proxy = self.vpn_provider.proxy(self.settings)
        if proxy:
            preferences.update({
                "proxy_type": "SOCKS5",
                "proxy_ip": proxy.host,
                "proxy_port": proxy.port,
                "proxy_peer_connections": True,
                "proxy_hostname_lookup": True,
                "proxy_bittorrent": True,
                "proxy_misc": True,
                "proxy_rss": True,
                "proxy_torrents_only": False,
            })
        else:
            preferences.update({
                "proxy_type": "None",
                "proxy_ip": "",
                "proxy_port": 0,
                "proxy_peer_connections": False,
                "proxy_hostname_lookup": False,
                "proxy_bittorrent": False,
                "proxy_misc": False,
                "proxy_rss": False,
                "proxy_torrents_only": False,
            })
        self.client.form(
            "POST", f"{base}/app/setPreferences",
            {"json": json.dumps(preferences)}, self._qbit_headers(),
        )
        selected_categories = {arr.category for arr in self.arrs}
        for category in (value for value in ("movies", "movies-4k", "tv", "tv-4k", "music") if value in selected_categories):
            try:
                self.client.form(
                    "POST", f"{base}/torrents/createCategory",
                    {"category": category, "savePath": f"/downloads/complete/{category}"},
                    self._qbit_headers(),
                )
            except RequestError as error:
                if error.status != 409:
                    raise
        route = f"{self.vpn_provider.name} SOCKS5" if proxy else "direct routing"
        category_count = "five" if len(selected_categories) == 5 else str(len(selected_categories))
        return f"{route}, shared paths, and {category_count} media categories are configured"

    def configure_sabnzbd(self, vpn_ok):
        url = self.settings.url("sabnzbd")
        key = self.settings.key("sabnzbd")
        if not key:
            return "waiting", "Waiting for SABnzbd to persist its API key"
        self._sab_call(url, key, {"mode": "version"})
        if not vpn_ok:
            return "waiting", f"Waiting for {self.vpn_provider.name} before applying network settings"
        whitelist_response = self._sab_call(
            url, key,
            {"mode": "get_config", "section": "misc", "keyword": "host_whitelist"},
        )
        whitelist_data = whitelist_response.json() if whitelist_response.body else {}
        whitelist = (
            whitelist_data.get("config", {}).get("misc", {}).get("host_whitelist", "")
            if isinstance(whitelist_data, dict) else ""
        )
        entries = (
            [str(value).strip() for value in whitelist]
            if isinstance(whitelist, list)
            else [value.strip() for value in str(whitelist).split(",")]
        )
        entries = [value for value in entries if value]
        internal_host = urlsplit(url).hostname
        if internal_host and internal_host not in entries:
            entries.append(internal_host)
            self._sab_call(
                url, key,
                {
                    "mode": "set_config",
                    "section": "misc",
                    "keyword": "host_whitelist",
                    "value": ",".join(entries),
                },
            )
        proxy = self.vpn_provider.proxy(self.settings)
        for keyword, value in {
            "socks5_proxy_url": f"socks5://{proxy.host}:{proxy.port}" if proxy else "",
            "complete_dir": "/downloads/complete",
            "download_dir": "/downloads/incomplete",
            "username": "",
            "password": "",
        }.items():
            self._sab_call(url, key, {"mode": "set_config", "section": "misc", "keyword": keyword, "value": value})
        selected_categories = {arr.category for arr in self.arrs}
        for category in (value for value in ("movies", "movies-4k", "tv", "tv-4k", "music") if value in selected_categories):
            self._sab_call(url, key, {"mode": "set_config", "section": "categories", "name": category, "dir": category})
        route = f"{self.vpn_provider.name} SOCKS5" if proxy else "direct routing"
        category_count = "five" if len(selected_categories) == 5 else str(len(selected_categories))
        return f"{route}, shared paths, and {category_count} media categories are configured"

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
        clients = []
        if "qbittorrent" in self.enabled_modules:
            self._ensure_download_client(arr, "QBittorrent", "Umbrel Arr qBittorrent", self.settings.url("qbittorrent"))
            clients.append("qBittorrent")
        if "sabnzbd" in self.enabled_modules:
            self._ensure_download_client(arr, "Sabnzbd", "Umbrel Arr SABnzbd", self.settings.url("sabnzbd"), self.settings.key("sabnzbd"))
            clients.append("SABnzbd")
        suffix = f" and {', '.join(clients)}" if clients else ""
        return f"Root {arr.root}{suffix} are configured"

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
        if implementation == "QBittorrent":
            values.update({
                "username": "admin",
                "password": self.settings.qbittorrent_password,
            })
        self._set_fields(payload, values)
        payload.update({"name": name, "enable": True, "priority": 1, "removeCompletedDownloads": True, "removeFailedDownloads": True, "tags": []})
        self._upsert(
            arr.api,
            "downloadclient",
            arr.api_key,
            payload,
            existing,
            owned_fields=values,
            owned_keys=(
                "name", "enable", "priority", "removeCompletedDownloads",
                "removeFailedDownloads", "tags",
            ),
        )

    def configure_prowlarr(self, vpn_ok):
        url = self.settings.url("prowlarr")
        key = self.settings.key("prowlarr")
        if not key:
            return "waiting", "Waiting for Prowlarr to persist its API key"
        api = f"{url}/api/v1"
        self.client.json("GET", f"{api}/system/status", key)
        proxy = self.vpn_provider.proxy(self.settings) if vpn_ok else None
        if vpn_ok:
            config = self.client.json("GET", f"{api}/config/host", key)
            desired_host = {
                "proxyEnabled": bool(proxy),
                "proxyType": "socks5" if proxy else config.get("proxyType", "http"),
                "proxyHostname": proxy.host if proxy else "",
                "proxyPort": proxy.port if proxy else 0,
                "proxyBypassFilter": ",".join(f"umbrel-arr-{slug}_server_1" for slug in self.enabled_modules),
                "proxyBypassLocalAddresses": True,
            }
            if any(config.get(name) != value for name, value in desired_host.items()):
                config.update(desired_host)
                self.client.json("PUT", f"{api}/config/host/{config.get('id', 1)}", key, config)
        if "flaresolverr" in self.enabled_modules:
            self._configure_flaresolverr_proxy(api, key)
        schemas = self.client.json("GET", f"{api}/applications/schema", key)
        existing = self.client.json("GET", f"{api}/applications", key)
        for arr in self.arrs:
            payload = self._schema(schemas, arr.implementation)
            values = {"prowlarrUrl": url, "baseUrl": arr.url, "apiKey": arr.api_key}
            self._set_fields(payload, values)
            payload.update({"name": f"Umbrel Arr {arr.name}", "syncLevel": "fullSync", "tags": []})
            self._upsert(
                api,
                "applications",
                key,
                payload,
                existing,
                owned_fields=values,
                owned_keys=("name", "syncLevel", "tags"),
            )
        network_note = f"{self.vpn_provider.name} routing and " if proxy else ""
        solver_note = "FlareSolverr plus " if "flaresolverr" in self.enabled_modules else ""
        return f"{network_note}{solver_note}{len(self.arrs)} full-sync Arr applications are configured"

    def _configure_flaresolverr_proxy(self, api, key):
        tags = self.client.json("GET", f"{api}/tag", key)
        tag = next((item for item in tags if item.get("label", "").casefold() == "flaresolverr"), None)
        if tag is None:
            tag = self.client.json("POST", f"{api}/tag", key, {"label": "flaresolverr"})
        schemas = self.client.json("GET", f"{api}/indexerproxy/schema", key)
        existing = self.client.json("GET", f"{api}/indexerproxy", key)
        payload = self._schema(schemas, "FlareSolverr")
        values = {"host": self.settings.url("flaresolverr"), "requestTimeout": 60}
        self._set_fields(payload, values)
        payload.update({"name": "Umbrel Arr FlareSolverr", "tags": [tag["id"]]})
        self._upsert(
            api,
            "indexerproxy",
            key,
            payload,
            existing,
            owned_fields=values,
            owned_keys=("name", "tags"),
        )

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
        proxy = self.vpn_provider.proxy(self.settings) if vpn_ok else None
        if proxy:
            values.update({
                "settings-proxy-type": "socks5",
                "settings-proxy-url": proxy.host,
                "settings-proxy-port": str(proxy.port),
                "settings-proxy-exclude": ["localhost", "127.0.0.1", urlsplit(self.settings.url("sonarr")).hostname, urlsplit(self.settings.url("radarr")).hostname],
            })
        else:
            values.update({
                "settings-proxy-type": "",
                "settings-proxy-url": "",
                "settings-proxy-port": "",
                "settings-proxy-exclude": [],
            })
        self.client.form("POST", f"{self.settings.url('bazarr')}/api/system/settings", values, {"X-API-KEY": key})
        return "HD Sonarr and Radarr are connected" + (f" through {self.vpn_provider.name}" if proxy else "")

    def configure_profilarr(self):
        url = self.settings.url("profilarr")
        form_headers = {"Origin": url, "Referer": f"{url}/"}
        self.client.json("GET", f"{url}/api/v1/status")
        databases = self.client.json("GET", f"{url}/api/v1/databases")
        database = next((item for item in databases if item.get("repository_url") == DATABASE_URL or item.get("name") == "Dictionarry"), None)
        if database is None:
            self.client.form("POST", f"{url}/databases/new", {"name": "Dictionarry", "repository_url": DATABASE_URL, "branch": "v2", "sync_strategy": "1440", "auto_pull": "1"}, form_headers)
            return "waiting", "Dictionarry database link queued; waiting for Profilarr to index it"
        video_arrs = [arr for arr in self.arrs if arr.slug in HD_UHD_VIDEO_APPS]
        instances = self.client.json("GET", f"{url}/api/v1/arr")
        current = {item.get("name"): item for item in instances}
        for arr in video_arrs:
            if arr.name not in current:
                self.client.form("POST", f"{url}/arr/new", {"name": arr.name, "type": arr.implementation.lower(), "url": arr.url, "external_url": self.settings.external_url(arr.slug), "api_key": arr.api_key, "tags": json.dumps(["4k" if arr.is_4k else "hd", MANAGED_TAG])}, form_headers)
        instances = self.client.json("GET", f"{url}/api/v1/arr")
        current = {item.get("name"): item for item in instances}
        missing = [arr.name for arr in video_arrs if arr.name not in current]
        if missing:
            return "waiting", f"Waiting for Profilarr Arr connections: {', '.join(missing)}"
        sync_marker_present = any(
            str(item.get("label", "")).casefold() == PROFILARR_SYNC_MARKER_TAG
            for item in self._prowlarr_tags()
        )
        for arr in video_arrs:
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
        return f"Dictionarry profiles and referenced custom formats sync daily to {len(video_arrs)} Arr instances"

    def configure_overseerr(self):
        url = self.settings.url("overseerr")
        key = self.settings.key("overseerr")
        public = self.client.json("GET", f"{url}/api/v1/settings/public")
        if not public.get("initialized"):
            return "action_required", "Complete the Plex sign-in in Overseerr; server registration will continue automatically"
        if not key:
            return "waiting", "Waiting for Overseerr to persist its API key"
        headers = {"X-API-Key": key}
        groups = {
            "sonarr": [arr for arr in self.arrs if arr.implementation == "Sonarr"],
            "radarr": [arr for arr in self.arrs if arr.implementation == "Radarr"],
        }
        for kind, arrs in groups.items():
            if not arrs:
                continue
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

    def _upsert(
        self, base, route, key, payload, existing,
        *, owned_fields=(), owned_keys=(),
    ):
        match = next((item for item in existing if item.get("name") == payload.get("name")), None)
        if match:
            merged = copy.deepcopy(match)
            desired_fields = {
                str(field.get("name", "")).casefold(): field
                for field in payload.get("fields", [])
            }
            merged_fields = merged.setdefault("fields", [])
            current_fields = {
                str(field.get("name", "")).casefold(): field
                for field in merged_fields
            }
            for name in owned_fields:
                normalized = str(name).casefold()
                desired = desired_fields.get(normalized)
                if desired is None:
                    continue
                current = current_fields.get(normalized)
                if current is None:
                    merged_fields.append(copy.deepcopy(desired))
                    current_fields[normalized] = merged_fields[-1]
                else:
                    current["value"] = copy.deepcopy(desired.get("value"))
            for name in owned_keys:
                if name in payload:
                    merged[name] = copy.deepcopy(payload[name])
            merged["id"] = match["id"]
            if merged == match:
                return match
            return self.client.json("PUT", f"{base}/{route}/{match['id']}", key, merged)
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
