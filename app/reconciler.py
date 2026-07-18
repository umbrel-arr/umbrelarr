import copy
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from api_keys import ApiKeyResolver
from catalog import (
    CORE_MODULES, DEFAULT_MODULES, MEDIA_MODULES, MEDIA_SERVER_MODULES, MODULES,
    SERVICE_MODULES, VIDEO_MODULES, dependencies_for, normalize_modules,
    validate_modules,
)
from http_client import HttpClient, RequestError
from state import VALID_STATES, RuntimeState, ServiceStatus
from storage import LOCAL_ROOTS, NETWORK_ROOTS, PRESETS, StorageSettings
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

MEDIA_LIBRARY_CONFIG = {
    "sonarr": {"name": "Umbrel Arr TV", "jellyfinType": "tvshows", "plexType": 2, "plexScanner": "Plex TV Series", "plexAgent": "tv.plex.agents.series"},
    "sonarr-4k": {"name": "Umbrel Arr TV 4K", "jellyfinType": "tvshows", "plexType": 2, "plexScanner": "Plex TV Series", "plexAgent": "tv.plex.agents.series"},
    "radarr": {"name": "Umbrel Arr Movies", "jellyfinType": "movies", "plexType": 1, "plexScanner": "Plex Movie", "plexAgent": "tv.plex.agents.movie"},
    "radarr-4k": {"name": "Umbrel Arr Movies 4K", "jellyfinType": "movies", "plexType": 1, "plexScanner": "Plex Movie", "plexAgent": "tv.plex.agents.movie"},
    "lidarr": {"name": "Umbrel Arr Music", "jellyfinType": "music", "plexType": 8, "plexScanner": "Plex Music", "plexAgent": "tv.plex.agents.music"},
}


APP_PORTS = {module.id: module.port for module in SERVICE_MODULES}
NAMES = {module.id: module.name for module in SERVICE_MODULES}
MEDIA_APPS = MEDIA_MODULES
HD_UHD_VIDEO_APPS = VIDEO_MODULES
# Compatibility exports describe the default 1.1 stack. Runtime requirements
# are derived from the user's selected modules instead.
REQUIRED_APPS = tuple(
    slug for slug in NAMES if slug != "umbrelarr" and slug in DEFAULT_MODULES
)
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
        env = os.environ if environ is None else environ
        self.env = env
        legacy_device_domain = env.get("DEVICE_DOMAIN_NAME", "umbrel.local").strip()
        configured_base_url = env.get("UMBREL_ARR_BASE_URL", "").strip()
        self.base_url = self._normalize_base_url(
            configured_base_url or f"http://{legacy_device_domain}"
        )
        self.device_domain = urlsplit(self.base_url).hostname
        self.interval = max(30, int(env.get("RECONCILE_INTERVAL", "300")))
        self.telemetry_interval = max(
            5, int(env.get("UMBREL_ARR_DOCKER_TELEMETRY_INTERVAL", "30"))
        )
        self.docker_broker_url = env.get(
            "UMBREL_ARR_DOCKER_BROKER_URL", ""
        ).strip().rstrip("/")
        self.docker_broker_token = env.get(
            "UMBREL_ARR_DOCKER_BROKER_TOKEN", ""
        ).strip()
        self.api_keys = ApiKeyResolver(env.get("UMBREL_ARR_MANAGED_CONFIG_DIR", "/managed-config"))
        self._runtime_urls = {}
        self._runtime_keys = {}
        self._runtime_key_sources = {}
        configured_modules = env.get("UMBREL_ARR_ENABLED_SERVICES", "").strip()
        self.modules_configured = bool(configured_modules)
        self.enabled_modules = normalize_modules(
            configured_modules.split(",") if configured_modules else CORE_MODULES
        )
        configured_provider = env.get("UMBREL_ARR_VPN_PROVIDER", "").strip()
        self.vpn_provider_configured = bool(configured_provider)
        self.vpn_provider_id = configured_provider or (
            "privado" if "privado-vpn" in self.enabled_modules else "direct"
        )

    @staticmethod
    def _normalize_base_url(value):
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as error:
            raise ValueError("UMBREL_ARR_BASE_URL must be a valid HTTP or HTTPS URL") from error
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or port is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "UMBREL_ARR_BASE_URL must be an HTTP or HTTPS origin without a port, credentials, path, query, or fragment"
            )
        hostname = parsed.hostname
        host = f"[{hostname}]" if ":" in hostname else hostname
        return f"{parsed.scheme}://{host}"

    def url(self, slug):
        runtime = self._runtime_urls.get(slug, "")
        if runtime:
            return runtime
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_URL"
        configured = self.env.get(key, "").strip().rstrip("/")
        return configured or self.external_url(slug)

    def url_is_configured(self, slug):
        if self._runtime_urls.get(slug):
            return True
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_URL"
        return bool(self.env.get(key, "").strip())

    def runtime_url_is_configured(self, slug):
        return bool(self._runtime_urls.get(slug))

    def key(self, slug):
        runtime = self._runtime_keys.get(slug, "")
        if runtime:
            return runtime
        key = self.api_key_environment_variable(slug)
        exported = self.env.get(key, "").strip()
        return exported or self.api_keys.resolve(slug)

    @staticmethod
    def api_key_environment_variable(slug):
        return f"UMBREL_ARR_{slug.upper().replace('-', '_')}_API_KEY"

    def credential_metadata(self, slug):
        """Describe credential availability without returning a secret value."""
        module = MODULES.get(slug)
        if module is not None and not module.requires_api_key:
            return {}
        environment_variable = self.api_key_environment_variable(slug)
        environment_configured = bool(
            self.env.get(environment_variable, "").strip()
        )
        if self._runtime_keys.get(slug):
            source = self._runtime_key_sources.get(slug, "ui")
            configured = True
        elif environment_configured:
            source = "environment"
            configured = True
        elif self.api_keys.resolve(slug):
            source = "managed_config"
            configured = True
        else:
            source = "missing"
            configured = False
        return {
            "apiKeyEnvironmentVariable": environment_variable,
            "credentialSource": source,
            "credentialConfigured": configured,
            "environmentCredentialConfigured": environment_configured,
        }

    def connection_overrides(self):
        return {
            "urls": dict(self._runtime_urls),
            "keys": dict(self._runtime_keys),
            "keySources": dict(self._runtime_key_sources),
        }

    def restore_connection_overrides(self, snapshot):
        snapshot = snapshot or {}
        self._runtime_urls = dict(snapshot.get("urls", {}))
        self._runtime_keys = dict(snapshot.get("keys", {}))
        self._runtime_key_sources = {
            slug: source
            for slug, source in snapshot.get("keySources", {}).items()
            if slug in self._runtime_keys and source in {"ui", "service_api"}
        }

    def set_runtime_key(self, slug, value, source="ui"):
        if source not in {"ui", "service_api"}:
            raise ValueError("Choose a supported runtime credential source")
        value = ApiKeyResolver._clean(value)
        if not value:
            raise ValueError(f"Enter a valid API key for {NAMES.get(slug, slug)}")
        self._runtime_keys[slug] = value
        self._runtime_key_sources[slug] = source

    def apply_connections(self, connections, selected_modules):
        if connections is None:
            return False
        if not isinstance(connections, dict):
            raise ValueError("connections must be a JSON object")
        selected = set(selected_modules)
        normalized = {}
        for slug, raw in connections.items():
            module = MODULES.get(slug)
            if module is None or slug == "umbrelarr" or slug not in selected:
                raise ValueError("Connection details must belong to a selected service")
            if not isinstance(raw, dict):
                raise ValueError(f"Connection details for {module.name} must be an object")
            address = str(raw.get("url", "")).strip()
            api_key = str(raw.get("apiKey", "")).strip()
            credential_source = str(raw.get("credentialSource", "")).strip()
            if credential_source not in {"", "environment", "ui"}:
                raise ValueError(
                    f"Choose environment or UI credentials for {module.name}"
                )
            if credential_source and not module.requires_api_key:
                raise ValueError(f"{module.name} does not use an API key")
            if credential_source == "environment" and api_key:
                raise ValueError(
                    f"Do not submit an API key when {module.name} uses an environment variable"
                )
            if address:
                if len(address) > 2048 or any(character.isspace() for character in address):
                    raise ValueError(f"Enter a valid service address for {module.name}")
                parsed = urlsplit(address)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(
                        f"{module.name} service address must be an HTTP or HTTPS URL without credentials, a query, or a fragment"
                    )
                address = address.rstrip("/")
            if api_key:
                if not module.requires_api_key:
                    raise ValueError(f"{module.name} does not use an API key")
                if len(api_key) > 512 or any(character.isspace() for character in api_key):
                    raise ValueError(f"Enter a valid API key for {module.name}")
            normalized[slug] = {
                "url": address,
                "apiKey": api_key,
                "credentialSource": credential_source,
            }

        changed = False
        for slug, values in normalized.items():
            address = values["url"]
            api_key = values["apiKey"]
            credential_source = values["credentialSource"]
            if address and self._runtime_urls.get(slug) != address:
                self._runtime_urls[slug] = address
                changed = True
            if credential_source == "environment":
                if self._runtime_keys.pop(slug, None):
                    changed = True
                self._runtime_key_sources.pop(slug, None)
            if api_key and self._runtime_keys.get(slug) != api_key:
                self.set_runtime_key(slug, api_key, "ui")
                changed = True
        return changed

    def clear_runtime_connection(self, slug):
        self._runtime_urls.pop(slug, None)
        self._runtime_keys.pop(slug, None)
        self._runtime_key_sources.pop(slug, None)

    def external_url(self, slug):
        port = APP_PORTS.get(slug)
        return f"{self.base_url}:{port}" if port else ""

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
        self._draft_modules = None
        self._draft_vpn_provider_id = ""
        self._draft_connection_restore = None
        self._setup_detection = []
        self._qbittorrent_cookie = ""
        self._container_services = {}
        self._container_updated_at = 0
        self._container_error = ""
        self._container_refresh_lock = threading.Lock()
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
            ServiceStatus(
                slug,
                NAMES[slug],
                role=MODULES[slug].role,
                link=self.settings.external_url(slug),
            )
            for slug in NAMES if slug in self.enabled_modules
        ]
        self.runtime = RuntimeState(services, dependencies)
        self.runtime.events = previous_events
        self.arrs = [arr for arr in self._arr_instances() if arr.slug in self.enabled_modules]
        self._apply_container_snapshot()

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
                media_results = {}
                for arr in self.arrs:
                    media_results[arr.slug] = self._step(arr.slug, self.configure_arr, arr)
            else:
                media_results = {arr.slug: False for arr in self.arrs}
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
            media_ready = bool(media_results) and all(media_results.values())
            for slug, callback in (("jellyfin", self.configure_jellyfin), ("plex", self.configure_plex)):
                if slug not in self.enabled_modules:
                    continue
                if media_ready:
                    self._step(slug, callback)
                else:
                    self.runtime.set(slug, "waiting", "Waiting for selected media managers and library storage")
            self.runtime.event("Reconciliation completed")
        finally:
            self.runtime.complete()

    def _mark_setup_required(self):
        self.runtime.set_unchecked(
            "umbrelarr", "action_required",
            "Choose the services you installed, then check and connect them",
        )
        for slug in self._selected_apps():
            self.runtime.set_unchecked(
                slug, "waiting", "Waiting for connection setup before the first health check",
            )

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
            selected_modules = self._draft_modules or self.enabled_modules
            provider_id = self._draft_vpn_provider_id or self.vpn_provider.id
            container_services = copy.deepcopy(self._container_services)
            container_updated_at = self._container_updated_at
            container_error = self._container_error
        provider = get_vpn_provider(provider_id)
        container_authoritative = bool(
            self.settings.docker_broker_url
            and container_updated_at
            and not container_error
        )
        if self.settings.docker_broker_url and container_error:
            apps = [
                self._detect_app(slug, {}, container_error)
                for slug in NAMES
                if slug != "umbrelarr" and slug in selected_modules
            ]
        detected = sum(item.get("detected", item["reachable"]) for item in apps)
        selected_apps = tuple(
            slug for slug in NAMES
            if slug != "umbrelarr" and slug in selected_modules
        )
        detection_complete = len(apps) == len(selected_apps)
        blocking = [
            item for item in apps
            if not item["reachable"] or (not item["credentials"] and item["id"] != "qbittorrent")
        ]
        vpn_status = self._vpn_setup_status(provider)
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

        def public_module(module):
            credential = self.settings.credential_metadata(module.id)
            return {
                **module.public(),
                "enabled": module.id in selected_modules,
                "active": module.id in self.enabled_modules,
                "installed": (
                    module.id in container_services
                    if container_authoritative else None
                ),
                "container": (
                    copy.deepcopy(container_services.get(module.id, {}))
                    if container_authoritative else {}
                ),
                "connectionUrl": self.settings.url(module.id),
                "connectionConfigured": self.settings.url_is_configured(module.id),
                **credential,
            }

        return {
            "phase": phase,
            "confirmed": confirmed,
            "canConfirm": can_confirm,
            "requiredCount": len(selected_apps),
            "selectedCount": len(selected_apps),
            "detectedCount": detected,
            "detectionComplete": detection_complete,
            "apps": apps,
            "enabledServices": list(selected_modules),
            "activeEnabledServices": list(self.enabled_modules),
            "modules": [
                public_module(module)
                for module in SERVICE_MODULES if module.id != "umbrelarr"
            ],
            "docker": {
                "configured": bool(self.settings.docker_broker_url),
                "available": bool(container_updated_at and not container_error),
                "updatedAt": container_updated_at,
                "error": container_error,
            },
            "vpnProvider": provider.id,
            "vpnProviders": [provider.public() for provider in VPN_PROVIDERS.values()],
            "vpnStatus": vpn_status,
            "configurationChanged": self._selection_dirty,
        }

    def _vpn_setup_status(self, provider=None):
        provider = provider or self.vpn_provider
        if provider.service_id:
            return {
                "ready": True,
                "status": "managed_app",
                "detail": f"{provider.name} health and login are managed after connection",
            }
        try:
            status, detail = provider.check(self.settings, self.client)
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
            # complete legacy stack remains selected with Privado unless the
            # deployment already supplied explicit module/provider defaults.
            selected = (
                self.settings.enabled_modules
                if self.settings.modules_configured else DEFAULT_MODULES
            )
            provider_id = (
                self.settings.vpn_provider_id
                if self.settings.modules_configured or self.settings.vpn_provider_configured
                else "privado"
            )
            self._set_modules(selected, provider_id)
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
            self._draft_modules = None
            self._draft_vpn_provider_id = ""
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
        # Create replacement markers before removing old ones. This keeps the
        # previous selection authoritative if Prowlarr rejects the first write,
        # and is especially important when changing VPN providers.
        for label in sorted(desired):
            if label not in existing:
                self.client.json("POST", f"{api}/tag", key, {"label": label})
        for label, item in existing.items():
            if managed(label) and label not in desired:
                self.client.json("DELETE", f"{api}/tag/{item['id']}", key)

    def refresh_container_state(self):
        """Single-flight a broker refresh across telemetry and setup requests."""
        if not self.settings.docker_broker_url:
            return False
        with self._container_refresh_lock:
            return self._refresh_container_state_locked()

    def _refresh_container_state_locked(self):
        """Refresh sanitized container inventory and metrics from the host broker."""
        if not self.settings.docker_broker_url:
            return False
        headers = {"Accept": "application/json"}
        if self.settings.docker_broker_token:
            headers["Authorization"] = f"Bearer {self.settings.docker_broker_token}"
        try:
            snapshot = self.client.json(
                "GET",
                f"{self.settings.docker_broker_url}/v1/snapshot",
                headers=headers,
            )
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("services"), dict):
                raise ValueError("Docker inventory returned an invalid snapshot")
            updated_at = snapshot.get("updatedAt") or int(time.time())
            if not isinstance(updated_at, (int, float, str)):
                raise ValueError("Docker inventory returned an invalid timestamp")
            services = {
                slug: copy.deepcopy(value)
                for slug, value in snapshot["services"].items()
                if slug in NAMES and isinstance(value, dict)
            }
        except (RequestError, OSError, TypeError, ValueError) as error:
            with self._setup_lock:
                self._container_error = self._safe_error(error)
            self._apply_container_snapshot()
            return False
        with self._setup_lock:
            self._container_services = services
            self._container_updated_at = updated_at
            self._container_error = ""
        self._apply_container_snapshot()
        return True

    def _apply_container_snapshot(self):
        runtime = getattr(self, "runtime", None)
        if runtime is None:
            return
        with self._setup_lock:
            services = copy.deepcopy(self._container_services)
            updated_at = self._container_updated_at
            error = self._container_error
        authoritative = bool(updated_at and not error)
        for slug in tuple(runtime.services):
            if self.settings.docker_broker_url and not authoritative:
                container = {
                    "state": "unknown",
                    "health": "unknown",
                    "updatedAt": updated_at,
                }
                if error:
                    container["error"] = error
                runtime.set_container(slug, container)
                runtime.retain_resources(slug)
                continue
            value = services.get(slug)
            if value is None:
                container = {}
                if self.settings.docker_broker_url:
                    container = {
                        "state": "unknown" if error else "not_installed",
                        "health": "unknown",
                        "updatedAt": updated_at,
                    }
                    if error:
                        container["error"] = error
                runtime.set_container(slug, container)
                runtime.set_resources(slug, {})
                continue
            container = {
                key: value[key]
                for key in ("id", "containerId", "name", "state", "health")
                if key in value
            }
            container["updatedAt"] = updated_at
            runtime.set_container(slug, container)
            resources = self._docker_resources(value, updated_at)
            if not resources:
                runtime.retain_resources(slug)
                continue
            runtime.set_resources(slug, resources)

    @staticmethod
    def _docker_resources(container, updated_at, sample_state="current"):
        raw = container.get("resources")
        if not isinstance(raw, dict):
            return {}
        memory = raw.get("memory") if isinstance(raw.get("memory"), dict) else {}
        block_io = raw.get("blockIO") if isinstance(raw.get("blockIO"), dict) else {}
        network = raw.get("network") if isinstance(raw.get("network"), dict) else {}
        cpu = {}
        if raw.get("cpuPercent") is not None:
            cpu = {
                "percent": raw.get("cpuPercent"),
                "onlineCpus": raw.get("onlineCpus"),
                "capacityPercent": raw.get("cpuCapacityPercent"),
            }
        if not any((cpu, memory, block_io, network)):
            return {}
        resources = {
            "source": "docker",
            "updatedAt": updated_at,
            "sampleState": sample_state,
        }
        if cpu:
            resources["cpu"] = cpu
        if memory:
            resources["memory"] = copy.deepcopy(memory)
        if block_io:
            resources["blockIo"] = copy.deepcopy(block_io)
        if network:
            resources["network"] = copy.deepcopy(network)
        return resources

    def dashboard_snapshot(self):
        """Return only services backed by local discovery or explicit connections."""
        snapshot = self.runtime.snapshot()
        with self._setup_lock:
            containers = copy.deepcopy(self._container_services)
            updated_at = self._container_updated_at
            error = self._container_error
        docker_configured = bool(self.settings.docker_broker_url)
        docker_available = bool(docker_configured and updated_at and not error)
        runtime_services = {item["id"]: item for item in snapshot["services"]}

        if docker_configured:
            visible_ids = set(containers)
            visible_ids.update(
                slug for slug in runtime_services
                if self.settings.runtime_url_is_configured(slug)
            )
            visible_ids.add("umbrelarr")
        else:
            visible_ids = {"umbrelarr"}
            visible_ids.update(
                slug for slug in runtime_services
                if self.settings.url_is_configured(slug)
            )

        services = []
        for module in SERVICE_MODULES:
            slug = module.id
            if slug not in visible_ids:
                continue
            if slug in runtime_services:
                service = copy.deepcopy(runtime_services[slug])
                service["managed"] = True
                service["discoverySource"] = (
                    "docker" if slug in containers else
                    "direct" if self.settings.url_is_configured(slug) else
                    "process"
                )
                services.append(service)
                continue
            container = containers.get(slug)
            if not isinstance(container, dict):
                continue
            container_state = {
                key: container[key]
                for key in ("id", "containerId", "name", "state", "health")
                if key in container
            }
            container_state["updatedAt"] = updated_at
            sample_state = "current" if docker_available else "last_sample"
            services.append({
                "id": slug,
                "name": module.name,
                "role": module.role,
                "status": "unknown",
                "detail": "Installed locally and available to manage",
                "link": self.settings.url(slug),
                "checked_at": 0,
                "checks": [],
                "container": container_state,
                "resources": self._docker_resources(
                    container, updated_at, sample_state,
                ),
                "dependencies": [],
                "waitingOn": [],
                "managed": False,
                "discoverySource": "docker",
            })

        counts = {state: 0 for state in VALID_STATES}
        for service in services:
            counts[service["status"]] += 1
        snapshot["services"] = services
        snapshot["counts"] = counts
        snapshot["inventory"] = {
            "mode": "docker" if docker_configured else "direct",
            "configured": docker_configured,
            "available": docker_available,
            "updatedAt": updated_at,
            "error": error,
            "discoveredCount": len(containers),
        }
        return snapshot

    def _container_inventory(self):
        with self._setup_lock:
            services = copy.deepcopy(self._container_services)
            updated_at = self._container_updated_at
            error = self._container_error
            if not updated_at or error:
                services = {}
            return (
                services,
                updated_at,
                error,
            )

    def detect_apps(self, selected_modules=None):
        selected_modules = selected_modules or self._draft_modules or self.enabled_modules
        selected_apps = tuple(
            slug for slug in NAMES
            if slug != "umbrelarr" and slug in selected_modules
        )
        containers = None
        inventory_error = ""
        if self.settings.docker_broker_url:
            self.refresh_container_state()
            containers, _updated_at, inventory_error = self._container_inventory()
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(selected_apps)))) as executor:
            futures = [
                executor.submit(self._detect_app, slug, containers, inventory_error)
                for slug in selected_apps
            ]
            apps = [future.result() for future in futures]
        with self._setup_lock:
            self._setup_detection = apps
        self.runtime.event(f"Detected {sum(item['detected'] for item in apps)} of {len(apps)} installed services")
        return self.setup_snapshot()

    def select_and_detect(self, enabled_services, vpn_provider, connections=None):
        selected = normalize_modules(
            self.enabled_modules if enabled_services is None else enabled_services
        )
        if vpn_provider:
            provider = get_vpn_provider(vpn_provider)
        elif "privado-vpn" in selected:
            provider = get_vpn_provider("privado")
        elif self.vpn_provider.id == "privado":
            provider = get_vpn_provider("direct")
        else:
            provider = self.vpn_provider
        selected = normalize_modules(
            (set(selected) - {"privado-vpn"}) | ({provider.service_id} if provider.service_id else set())
        )
        errors = validate_modules(selected)
        if errors:
            raise ValueError("; ".join(errors))
        changed = selected != self.enabled_modules or provider.id != self.vpn_provider.id
        with self._setup_lock:
            if connections is not None and self._draft_connection_restore is None:
                self._draft_connection_restore = self.settings.connection_overrides()
            connections_changed = self.settings.apply_connections(connections, selected)
            self._draft_modules = selected if changed else None
            self._draft_vpn_provider_id = provider.id if changed else ""
            self._selection_dirty = changed or connections_changed
            self._setup_detection = []
        return self.detect_apps(selected)

    def cancel_selection_change(self):
        with self._setup_lock:
            if self._draft_connection_restore is not None:
                self.settings.restore_connection_overrides(self._draft_connection_restore)
            self._draft_connection_restore = None
            self._draft_modules = None
            self._draft_vpn_provider_id = ""
            self._selection_dirty = False
            self._setup_detection = []
        return self.setup_snapshot()

    def bootstrap_credential(self, service_id, username, password):
        """Create a dedicated credential through an explicitly authorized service API."""
        if service_id != "jellyfin":
            raise ValueError("Automatic credential creation is supported only for Jellyfin")
        username = str(username or "").strip()
        password = str(password or "")
        if not username or len(username) > 128 or any(ord(character) < 32 for character in username):
            raise ValueError("Enter a valid Jellyfin administrator username")
        if not password or len(password) > 512 or "\x00" in password:
            raise ValueError("Enter the Jellyfin administrator password")

        with self._setup_lock:
            selected = self._draft_modules or self.enabled_modules
            detected = next(
                (dict(item) for item in self._setup_detection if item.get("id") == service_id),
                None,
            )
        if service_id not in selected:
            raise ValueError("Choose Jellyfin before creating its API key")
        if detected is None:
            raise ValueError("Check Jellyfin before creating its API key")
        if not detected.get("reachable"):
            raise ValueError("Jellyfin must be reachable before creating its API key")
        metadata = self.settings.credential_metadata(service_id)
        if metadata["environmentCredentialConfigured"]:
            variable = metadata["apiKeyEnvironmentVariable"]
            raise ValueError(
                f"{variable} is configured but was rejected. Replace or remove it and restart umbrelarr before creating another key."
            )
        if detected.get("credentials") or detected.get("action") != "create_api_key":
            raise ValueError("Jellyfin does not currently need a new API key")

        url = self.settings.url(service_id).rstrip("/")
        client_header = (
            'MediaBrowser Client="umbrelarr", Device="umbrelarr", '
            'DeviceId="umbrelarr-setup", Version="1.0"'
        )
        admin_token = ""
        api_key = ""
        try:
            try:
                authentication = self.client.json(
                    "POST",
                    f"{url}/Users/AuthenticateByName",
                    payload={"Username": username, "Pw": password},
                    headers={"Authorization": client_header},
                )
            except RequestError as error:
                if error.status in {401, 403}:
                    raise ValueError("Jellyfin rejected the administrator username or password") from None
                raise RuntimeError("Jellyfin could not authenticate the administrator account") from None
            if not isinstance(authentication, dict):
                raise RuntimeError("Jellyfin returned an invalid authentication response")
            admin_token = ApiKeyResolver._clean(
                authentication.get("AccessToken", authentication.get("accessToken", ""))
            )
            if not admin_token:
                raise RuntimeError("Jellyfin did not return an administrator session")
            admin_headers = {"X-Emby-Token": admin_token}

            try:
                user = self.client.json("GET", f"{url}/Users/Me", headers=admin_headers)
            except RequestError as error:
                if error.status in {401, 403}:
                    raise ValueError("Jellyfin did not grant administrator access") from None
                raise RuntimeError("Jellyfin could not verify administrator access") from None
            user = user if isinstance(user, dict) else {}
            policy = user.get("Policy", user.get("policy", {}))
            is_administrator = isinstance(policy, dict) and bool(
                policy.get("IsAdministrator", policy.get("isAdministrator", False))
            )
            if not is_administrator:
                raise ValueError("Use a Jellyfin administrator account to create the API key")

            def named_keys():
                try:
                    result = self.client.json("GET", f"{url}/Auth/Keys", headers=admin_headers)
                except RequestError as error:
                    if error.status in {401, 403}:
                        raise ValueError("Jellyfin did not grant API-key administration access") from None
                    raise RuntimeError("Jellyfin could not list its API keys") from None
                if isinstance(result, dict):
                    items = result.get("Items", result.get("items", []))
                elif isinstance(result, list):
                    items = result
                else:
                    items = []
                matches = []
                for item in items if isinstance(items, list) else []:
                    if not isinstance(item, dict):
                        continue
                    name = item.get(
                        "Name",
                        item.get("name", item.get("AppName", item.get("appName", ""))),
                    )
                    if str(name).strip().casefold() == "umbrelarr":
                        matches.append(item)
                return matches

            matches = named_keys()
            if len(matches) > 1:
                raise ValueError(
                    "Jellyfin has multiple API keys named umbrelarr. Remove the duplicates in Jellyfin and try again."
                )
            if not matches:
                try:
                    self.client.json(
                        "POST",
                        f"{url}/Auth/Keys?{urlencode({'app': 'umbrelarr'})}",
                        headers=admin_headers,
                    )
                except RequestError as error:
                    if error.status in {401, 403}:
                        raise ValueError("Jellyfin did not grant API-key creation access") from None
                    raise RuntimeError("Jellyfin could not create the dedicated API key") from None
                matches = named_keys()
            if len(matches) != 1:
                raise RuntimeError("Jellyfin did not return the dedicated umbrelarr API key")
            api_key = ApiKeyResolver._clean(
                matches[0].get(
                    "AccessToken",
                    matches[0].get("accessToken", matches[0].get("Key", matches[0].get("key", ""))),
                )
            )
            if not api_key:
                raise RuntimeError("Jellyfin returned an invalid dedicated API key")
            try:
                self.client.json(
                    "GET", f"{url}/System/Info", headers={"X-Emby-Token": api_key},
                )
            except RequestError:
                raise ValueError(
                    "Jellyfin rejected the dedicated umbrelarr API key. Revoke it in Jellyfin and try again."
                ) from None
            self.settings.set_runtime_key(service_id, api_key, "service_api")
        finally:
            if admin_token:
                try:
                    self.client.json(
                        "POST", f"{url}/Sessions/Logout",
                        headers={"X-Emby-Token": admin_token},
                    )
                except (RequestError, OSError, ValueError):
                    pass

        self.runtime.event("Jellyfin API key connected through its administrator API")
        return self.detect_apps(selected)

    def remove_service(self, slug):
        module = MODULES.get(slug)
        if module is None:
            raise ValueError("Choose a known managed service")
        if module.required:
            raise ValueError(f"{module.name} is required by umbrelarr and cannot be removed")
        if not self.ensure_setup_ready():
            raise RuntimeError("Complete explicit setup before removing managed services")
        if slug not in self.enabled_modules:
            # Removing an already-absent service is intentionally idempotent.
            return self.setup_snapshot()

        selected = normalize_modules(set(self.enabled_modules) - {slug})
        provider_id = "direct" if self.vpn_provider.service_id == slug else self.vpn_provider.id
        errors = validate_modules(selected)
        if errors:
            raise ValueError(
                f"Cannot remove {module.name}: {'; '.join(errors)}. "
                "Remove the dependent service first."
            )

        # Prowlarr is the durable source of truth. Do not change the active
        # runtime until its markers accept the new selection.
        try:
            self._replace_module_markers(selected, provider_id)
        except (RequestError, OSError) as error:
            raise RuntimeError(
                "Unable to save the managed service selection in Prowlarr: "
                f"{self._safe_error(error)}"
            ) from error
        self._set_modules(selected, provider_id)
        self.settings.clear_runtime_connection(slug)
        with self._setup_lock:
            self._selection_dirty = False
            self._draft_modules = None
            self._draft_vpn_provider_id = ""
            self._draft_connection_restore = None
            self._setup_detection = []
        self.runtime.event(
            f"Stopped managing {module.name}; the installed app and its settings were left unchanged"
        )
        self.reconcile_async()
        return self.setup_snapshot()

    def _detect_app(self, slug, containers=None, inventory_error=""):
        container = None
        if containers is not None:
            if inventory_error:
                return {
                    "id": slug,
                    "name": NAMES[slug],
                    "reachable": False,
                    "credentials": False,
                    "action": "docker_unavailable",
                    "detected": False,
                    "detail": f"Docker inventory is unavailable: {inventory_error}",
                    "link": self.settings.url(slug),
                    "container": {"state": "unknown", "health": "unknown"},
                }
            value = containers.get(slug)
            if value is None:
                return {
                    "id": slug,
                    "name": NAMES[slug],
                    "reachable": False,
                    "credentials": False,
                    "action": "install_or_start",
                    "detected": False,
                    "detail": "Service is not installed",
                    "link": self.settings.url(slug),
                    "container": {"state": "not_installed", "health": "unknown"},
                }
            container = {
                key: value[key]
                for key in ("id", "containerId", "name", "state", "health")
                if key in value
            }
            state = str(container.get("state", "unknown")).casefold()
            if state != "running":
                return {
                    "id": slug,
                    "name": NAMES[slug],
                    "reachable": False,
                    "credentials": False,
                    "action": "start_service",
                    "detected": True,
                    "detail": f"App is installed but its container is {state.replace('_', ' ')}",
                    "link": self.settings.url(slug),
                    "container": container,
                }
        url = self.settings.url(slug)
        reachable = False
        probe_succeeded = False
        credential_action = ""
        detail = "App was not reachable"
        if url:
            try:
                probes = {
                    "qbittorrent": "/api/v2/app/version",
                    "jellyfin": "/System/Info/Public",
                    "plex": "/identity",
                    "privado-vpn": "/api/status",
                    "profilarr": "/api/v1/status",
                    "overseerr": "/api/v1/settings/public",
                }
                probe = f"{url}{probes.get(slug, '/')}"
                response = self.client.request("GET", probe, timeout=3)
                reachable = True
                redirected = urlsplit(getattr(response, "url", "") or probe)
                if (
                    redirected.hostname == urlsplit(self.settings.external_url(slug)).hostname
                    and redirected.port == 2000
                ):
                    credential_action = "direct_connection_required"
                    detail = (
                        "This address opens a platform login instead of the service API. "
                        "Enter a direct service address and check again."
                    )
                else:
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
        if credential_action == "direct_connection_required":
            credentials = False
        if reachable and credentials and slug != "qbittorrent":
            try:
                self._validate_detected_connection(slug)
            except RequestError as error:
                credentials = False
                if error.status in {401, 403}:
                    credential_action = "invalid_credentials"
                    detail = (
                        "The API key was rejected. Enter a current key and check again"
                    )
                elif error.status is None:
                    reachable = False
                    detail = "App stopped responding during its connection check"
                else:
                    credential_action = "connection_error"
                    detail = f"Connection check failed: {self._safe_error(error)}"
            except (OSError, ValueError) as error:
                credentials = False
                credential_action = "connection_error"
                detail = f"Connection check failed: {self._safe_error(error)}"
        if reachable and credentials and slug in KEYED_APPS:
            source = self.settings.credential_metadata(slug)["credentialSource"]
            if source == "managed_config":
                detail = (
                    "Existing Plex token connected automatically"
                    if slug == "plex" else
                    "API key connected automatically from the installed app"
                )
            elif source == "service_api":
                detail = "Dedicated umbrelarr API key created and verified"
            elif source == "environment":
                detail = "Environment API key verified"
            elif source == "ui":
                detail = "UI-provided API key verified for this process"
        if reachable and not credentials and slug != "qbittorrent":
            if credential_action:
                pass
            elif slug == "jellyfin":
                detail = "Create and connect a dedicated Jellyfin API key with an administrator account"
            elif slug == "plex":
                detail = "Claim or sign in to this Plex server, then enter its token above"
            elif slug == "overseerr":
                detail = "Complete Plex sign-in in Overseerr, then enter its API key above"
            elif MODULES[slug].credential_setup == "generated":
                detail = (
                    "The app has not exposed its generated API key yet. Wait for it to finish starting, "
                    "or provide the key through an environment variable or the UI"
                )
            else:
                detail = (
                    "Service found. Enter its API key above and check again"
                )
        action = "none"
        if not reachable:
            action = "connection_error" if container else "install_or_start"
        elif not credentials:
            actions = {
                "qbittorrent": "temporary_password_required",
                "jellyfin": "create_api_key",
                "plex": "claim_server",
                "overseerr": "complete_sign_in",
            }
            action = credential_action or actions.get(slug, "wait_for_api_key")
        return {
            "id": slug,
            "name": NAMES[slug],
            "reachable": reachable,
            "credentials": credentials,
            "action": action,
            "detected": bool(container) if containers is not None else reachable,
            "detail": detail,
            "link": self.settings.url(slug),
            "container": container or {},
        }

    def _validate_detected_connection(self, slug):
        """Validate an existing connection using read-only service APIs."""
        key = self.settings.key(slug)
        if slug in {arr.slug for arr in self._arr_instances()}:
            arr = next(arr for arr in self._arr_instances() if arr.slug == slug)
            self.client.json("GET", f"{arr.api}/system/status", key)
        elif slug == "prowlarr":
            self.client.json(
                "GET", f"{self.settings.url(slug)}/api/v1/system/status", key,
            )
        elif slug == "sabnzbd":
            query = urlencode({"mode": "version", "apikey": key, "output": "json"})
            parsed = urlsplit(self.settings.url(slug))
            trusted_host = "localhost" if parsed.port is None else f"localhost:{parsed.port}"
            self.client.request(
                "GET", f"{self.settings.url(slug)}/api?{query}",
                headers={"Host": trusted_host}, timeout=5,
            )
        elif slug == "bazarr":
            self.client.json(
                "GET", f"{self.settings.url(slug)}/api/system/status", key,
            )
        elif slug == "jellyfin":
            self.client.json(
                "GET", f"{self.settings.url(slug)}/System/Info",
                headers={"X-Emby-Token": key},
            )
        elif slug == "plex":
            self.client.json(
                "GET", f"{self.settings.url(slug)}/library/sections",
                headers={"X-Plex-Token": key},
            )
        elif slug == "overseerr":
            self.client.json(
                "GET", f"{self.settings.url(slug)}/api/v1/settings/main",
                headers={"X-API-Key": key},
            )

    def confirm_setup(
        self, storage_mode="", root_ids=None,
        qbittorrent_username="admin", qbittorrent_temporary_password="",
        enabled_services=None, vpn_provider="",
    ):
        was_ready = self.ensure_setup_ready()
        with self._setup_lock:
            expected_modules = self._draft_modules or self.enabled_modules
            expected_provider_id = self._draft_vpn_provider_id or self.vpn_provider.id
        selected = normalize_modules(
            expected_modules if enabled_services is None else enabled_services
        )
        provider_id = vpn_provider or expected_provider_id
        provider = get_vpn_provider(provider_id)
        selected = normalize_modules(
            (set(selected) - {"privado-vpn"}) | ({provider.service_id} if provider.service_id else set())
        )
        errors = validate_modules(selected)
        if errors:
            raise ValueError("; ".join(errors))
        if selected != expected_modules or provider_id != expected_provider_id:
            raise ValueError("Module selection changed; run detection again before connecting apps")
        snapshot = (
            self.detect_apps(selected)
            if self.settings.docker_broker_url
            else self.setup_snapshot()
        )
        if self.settings.docker_broker_url and not snapshot["docker"]["available"]:
            detail = snapshot["docker"].get("error") or "no current snapshot"
            raise ValueError(f"Docker inventory is unavailable: {detail}")
        if not snapshot["detectionComplete"]:
            raise ValueError("Detect installed apps before connecting them")
        missing = [item["name"] for item in snapshot["apps"] if not item["reachable"]]
        if missing:
            raise ValueError(f"Install or start these required apps first: {', '.join(missing)}")
        connection_issues = [
            item["name"] for item in snapshot["apps"]
            if item["id"] != "qbittorrent" and not item["credentials"]
        ]
        if connection_issues:
            raise ValueError(
                "Resolve these service connections before applying: "
                + ", ".join(connection_issues)
            )
        if not snapshot["vpnStatus"]["ready"]:
            raise ValueError(snapshot["vpnStatus"]["detail"])
        selected_arrs = [
            arr for arr in self._arr_instances()
            if arr.slug in selected
        ]
        if selected_arrs and not storage_mode:
            detected_storage = self.storage_snapshot()
            detected_mode = detected_storage.get("mode")
            if detected_storage.get("actionRequired") or detected_mode not in {*PRESETS, "adopted"}:
                storage_mode = "local"
                root_ids = {}
            else:
                storage_mode = "adopt" if detected_mode == "adopted" else detected_mode
                root_ids = detected_storage.get("rootIds", {})
        if selected_arrs:
            self._validate_storage_selection(
                storage_mode, root_ids or {}, selected, selected_arrs,
            )
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
        previous_modules = self.enabled_modules
        previous_provider = self.vpn_provider
        previous_runtime = self.runtime
        previous_arrs = self.arrs
        self._set_modules(selected, provider_id)
        try:
            # A first setup persists the reviewed selection immediately so an
            # interrupted credential handoff can resume after a restart. A
            # later fleet edit leaves the active markers untouched until every
            # new connection has passed its apply step.
            if not was_ready:
                self._replace_module_markers(selected, provider_id)
            if "qbittorrent" in self.enabled_modules:
                self._onboard_qbittorrent(
                    qbittorrent_username, qbittorrent_temporary_password,
                )
            if self.arrs:
                self._apply_storage(storage_mode, root_ids or {})
            if was_ready:
                self._replace_module_markers(selected, provider_id)
            tags = self.client.json("GET", f"{api}/tag", key)
            if not any(item.get("label", "").casefold() == SETUP_READY_MARKER_TAG for item in tags):
                self.client.json("POST", f"{api}/tag", key, {"label": SETUP_READY_MARKER_TAG})
        except Exception:
            if was_ready:
                self.enabled_modules = previous_modules
                self.vpn_provider = previous_provider
                self.runtime = previous_runtime
                self.arrs = previous_arrs
                self.storage.set_enabled_modules(previous_modules)
            else:
                self._mark_setup_required()
            raise
        with self._setup_lock:
            self._setup_ready = True
            self._selection_dirty = False
            self._draft_modules = None
            self._draft_vpn_provider_id = ""
            self._draft_connection_restore = None
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
        with self._setup_lock:
            selected = self._draft_modules or self.enabled_modules
        selected_arrs = [
            arr for arr in self._arr_instances()
            if arr.slug in selected
        ]
        folders = self._read_root_folders(required=False, arrs=selected_arrs)
        mode, root_ids = self._storage_marker_selection(self._prowlarr_tags(required=False))
        if selected == self.enabled_modules:
            target = self.storage
        else:
            target = StorageSettings()
            target.set_enabled_modules(selected)
        return target.update_from_apis(folders, mode, root_ids)

    def save_storage(self, mode, root_ids):
        if not self.ensure_setup_ready():
            raise RuntimeError("Complete explicit setup before changing library roots")
        snapshot = self._apply_storage(mode, root_ids)
        self.runtime.event(f"Library layout applied through service APIs for {mode} storage")
        self.reconcile_async()
        return snapshot

    def browse_library_filesystem(self, library_key, path="/"):
        if library_key not in LOCAL_ROOTS or library_key not in self.enabled_modules:
            raise ValueError("Choose a managed media library")
        arr = next(item for item in self.arrs if item.slug == library_key)
        if not arr.url or not arr.api_key:
            raise ValueError(f"{arr.name} API credentials are not available")
        path = str(path or "/").strip() or "/"
        if len(path) > 1024 or not Path(path).is_absolute():
            raise ValueError("Choose an absolute folder path")
        try:
            values = self._filesystem_contents(arr, path)
        except (RequestError, OSError) as error:
            raise ValueError(
                f"Unable to browse {arr.name}: {self._safe_error(error)}"
            ) from error
        if isinstance(values, dict):
            directories = values.get("directories", values.get("Directories", []))
            parent = values.get("parent", values.get("Parent"))
        elif isinstance(values, list):
            directories = values
            parent = str(Path(path).parent) if path != "/" else None
        else:
            directories = []
            parent = None
        normalized = []
        seen = set()
        for item in directories if isinstance(directories, list) else []:
            if not isinstance(item, dict):
                continue
            item_path = str(item.get("path", item.get("Path", ""))).rstrip("/") or "/"
            if not Path(item_path).is_absolute() or item_path in seen:
                continue
            seen.add(item_path)
            normalized.append({
                "name": str(item.get("name", item.get("Name", ""))) or Path(item_path).name or item_path,
                "path": item_path,
            })
        normalized.sort(key=lambda item: item["name"].casefold())
        parent = (str(parent).rstrip("/") or "/") if parent else None
        mounts = self.library_mount_checks(path, {library_key: values})
        return {
            "path": path.rstrip("/") or "/",
            "parent": parent,
            "directories": normalized,
            "service": arr.name,
            "mounts": mounts,
            "allMounted": bool(mounts) and all(item["status"] == "match" for item in mounts),
        }

    def _filesystem_contents(self, arr, path):
        query = urlencode({
            "path": path,
            "includeFiles": "false",
            "allowFoldersWithoutTrailingSlashes": "true",
        })
        return self.client.json("GET", f"{arr.api}/filesystem?{query}", arr.api_key)

    def library_mount_checks(self, path, known=None):
        path = str(path or "/").strip().rstrip("/") or "/"
        if len(path) > 1024 or not Path(path).is_absolute():
            raise ValueError("Choose an absolute folder path")
        known = known or {}

        def check(arr):
            if not arr.url or not arr.api_key:
                return {"id": arr.slug, "name": arr.name, "status": "unavailable", "detail": "API credentials unavailable"}
            try:
                if arr.slug not in known:
                    self._filesystem_contents(arr, path)
                return {"id": arr.slug, "name": arr.name, "status": "match", "detail": "Same path is available"}
            except (RequestError, OSError, ValueError) as error:
                return {"id": arr.slug, "name": arr.name, "status": "missing", "detail": self._safe_error(error)}

        arrs = list(self.arrs)
        if not arrs:
            return []
        with ThreadPoolExecutor(max_workers=len(arrs)) as executor:
            return list(executor.map(check, arrs))

    def save_library_storage(self, library_key, source, root_id=None, path=None):
        if not self.ensure_setup_ready():
            raise RuntimeError("Complete explicit setup before changing library roots")
        if library_key not in LOCAL_ROOTS or library_key not in self.enabled_modules:
            raise ValueError("Choose a managed media library")
        if source not in {"local", "network", "existing", "custom"}:
            raise ValueError("Library source must be Umbrel storage, network storage, or a system folder")

        current = self.storage_snapshot()
        if current["actionRequired"] or set(current["rootIds"]) != {
            arr.slug for arr in self.arrs
        }:
            raise ValueError("Resolve every library root before changing an individual library")
        selected_ids = dict(current["rootIds"])
        arr = next(item for item in self.arrs if item.slug == library_key)

        if source == "existing":
            try:
                selected_id = int(root_id)
            except (TypeError, ValueError) as error:
                raise ValueError("Choose an existing root for this library") from error
            candidates = current["candidates"].get(library_key, [])
            match = next((item for item in candidates if item["id"] == selected_id), None)
            if match is None:
                raise ValueError("The selected root is not available in this library's app")
            selected_path = match["path"]
        else:
            if source == "local":
                selected_path = LOCAL_ROOTS[library_key]
            elif source == "network":
                selected_path = NETWORK_ROOTS[library_key]
            else:
                selected_path = str(path or "").strip()
                if not selected_path:
                    raise ValueError("Choose a system folder for this library")
                selected_path = selected_path.rstrip("/") or "/"

        mount_checks = self.library_mount_checks(selected_path)
        unmatched = [item["name"] for item in mount_checks if item["status"] != "match"]
        if unmatched:
            raise ValueError(
                f"{selected_path} must be mounted at the same path in every managed media service; "
                f"check {', '.join(unmatched)}"
            )

        if source != "existing":
            self._ensure_root(arr, selected_path)
            folders = self._read_root_folders(required=True, arrs=[arr])[library_key]
            match = next(
                (item for item in folders if str(item.get("path", "")).rstrip("/") == selected_path.rstrip("/")),
                None,
            )
            if match is None or match.get("id") is None:
                raise RuntimeError("The selected root was not accepted by the library app")
            selected_id = int(match["id"])

        selected_ids[library_key] = selected_id
        snapshot = self._apply_storage("adopted", selected_ids)
        self.runtime.event(f"{arr.name} library root updated through its service API")
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

    def _validate_storage_selection(self, mode, root_ids, enabled=None, arrs=None):
        normalized = "adopted" if mode == "adopt" else mode
        if normalized not in {*PRESETS, "adopted"}:
            raise ValueError("Storage mode must be local, network, or adopt")
        if normalized != "adopted":
            return
        folders = self._read_root_folders(required=True, arrs=arrs)
        cleaned_ids = {
            slug: int(value) for slug, value in root_ids.items()
            if slug in LOCAL_ROOTS and str(value).strip()
        }
        candidate_storage = StorageSettings()
        candidate_storage.set_enabled_modules(enabled or self.enabled_modules)
        candidate = candidate_storage.update_from_apis(folders, "adopted", cleaned_ids)
        if candidate["actionRequired"]:
            raise ValueError("Choose one existing root-folder ID for every library")

    def _read_root_folders(self, required, arrs=None):
        folders = {}
        for arr in self.arrs if arrs is None else arrs:
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

    def _ensure_root(self, arr, root=None):
        root = root or arr.root
        existing = self.client.json("GET", f"{arr.api}/rootfolder", arr.api_key)
        if not any(item.get("path", "").rstrip("/") == root.rstrip("/") for item in existing):
            payload = {"path": root}
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
                payload["name"] = Path(root).name.replace("-", " ").title() or "Music"
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

    def _selected_media_libraries(self):
        return [
            (arr, MEDIA_LIBRARY_CONFIG[arr.slug])
            for arr in self.arrs if arr.slug in MEDIA_LIBRARY_CONFIG
        ]

    def configure_jellyfin(self):
        url = self.settings.url("jellyfin")
        key = self.settings.key("jellyfin")
        if not key:
            return "action_required", "Create a Jellyfin API key named umbrelarr, then restart umbrelarr"
        headers = {"X-Emby-Token": key}
        folders = self.client.json("GET", f"{url}/Library/VirtualFolders", headers=headers) or []
        existing = {
            str(folder.get("Name", "")): folder
            for folder in folders if isinstance(folder, dict)
        }
        created = 0
        paths_added = 0
        for arr, config in self._selected_media_libraries():
            name = config["name"]
            folder = existing.get(name)
            locations = {
                str(path).rstrip("/")
                for path in (folder or {}).get("Locations", []) if path
            }
            if folder is None:
                query = urlencode({
                    "name": name,
                    "collectionType": config["jellyfinType"],
                    "refreshLibrary": "false",
                })
                self.client.json(
                    "POST", f"{url}/Library/VirtualFolders?{query}",
                    payload={"LibraryOptions": {}}, headers=headers,
                )
                created += 1
            if arr.root.rstrip("/") not in locations:
                self.client.json(
                    "POST", f"{url}/Library/VirtualFolders/Paths?refreshLibrary=false",
                    payload={"Name": name, "Path": arr.root}, headers=headers,
                )
                paths_added += 1
        return f"{len(self.arrs)} managed libraries are current ({created} created, {paths_added} paths added)"

    def configure_plex(self):
        url = self.settings.url("plex")
        token = self.settings.key("plex")
        if not token:
            return "action_required", "Claim or sign in to this Plex server, then restart umbrelarr"
        headers = {"X-Plex-Token": token}
        response = self.client.json("GET", f"{url}/library/sections", headers=headers) or {}
        container = response.get("MediaContainer", {}) if isinstance(response, dict) else {}
        directories = container.get("Directory", []) if isinstance(container, dict) else []
        if isinstance(directories, dict):
            directories = [directories]
        existing = {
            str(directory.get("title", "")): directory
            for directory in directories if isinstance(directory, dict)
        }
        created = 0
        conflicts = []
        for arr, config in self._selected_media_libraries():
            name = config["name"]
            section = existing.get(name)
            locations = (section or {}).get("Location", [])
            if isinstance(locations, dict):
                locations = [locations]
            paths = {
                str(location.get("path", "")).rstrip("/")
                for location in locations if isinstance(location, dict)
            }
            if section is not None:
                if arr.root.rstrip("/") not in paths:
                    conflicts.append(name)
                continue
            query = urlencode({
                "name": name,
                "type": config["plexType"],
                "scanner": config["plexScanner"],
                "agent": config["plexAgent"],
                "language": "en-US",
                "locations": [arr.root],
            }, doseq=True)
            self.client.json("POST", f"{url}/library/sections?{query}", headers=headers)
            created += 1
        if conflicts:
            return (
                "action_required",
                "These Umbrel Arr Plex libraries use a different path: " + ", ".join(conflicts),
            )
        return f"{len(self.arrs)} managed libraries are current ({created} created)"

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


class DockerTelemetryLoop:
    def __init__(self, reconciler):
        self.reconciler = reconciler
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            self.reconciler.refresh_container_state()
            self.stop_event.wait(self.reconciler.settings.telemetry_interval)
