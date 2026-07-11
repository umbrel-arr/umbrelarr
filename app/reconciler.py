import copy
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from http_client import HttpClient, RequestError
from state import OwnershipState, RuntimeState, ServiceStatus
from storage import StorageSettings


MANAGED_TAG = "umbrel-arr-managed"
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
    "setup": 30992,
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
    "setup": "umbrelarr",
    "lidarr": "Lidarr",
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
        self.state_dir = Path(env.get("STATE_DIR", "/data"))
        self.interval = max(30, int(env.get("RECONCILE_INTERVAL", "300")))

    def url(self, slug):
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_URL"
        return self.env.get(key, "").rstrip("/")

    def key(self, slug):
        key = f"UMBREL_ARR_{slug.upper().replace('-', '_')}_API_KEY"
        return self.env.get(key, "").strip()

    def external_url(self, slug):
        return f"http://{self.device_domain}:{APP_PORTS[slug]}"


class Reconciler:
    def __init__(self, settings=None, client=None):
        self.settings = settings or Settings()
        self.client = client or HttpClient()
        services = [
            ServiceStatus(slug, NAMES[slug], link=self.settings.external_url(slug))
            for slug in NAMES
        ]
        self.runtime = RuntimeState(services)
        self.ownership = OwnershipState(self.settings.state_dir / "ownership.json")
        self.storage = StorageSettings(self.settings.state_dir / "storage.json")
        self.arrs = self._arr_instances()

    def _arr_instances(self):
        return [
            ArrInstance("sonarr", "Sonarr", "Sonarr", self.settings.url("sonarr"), self.settings.key("sonarr"), "v3", self.storage.root("sonarr"), "tv", 30985),
            ArrInstance("sonarr-4k", "Sonarr 4K", "Sonarr", self.settings.url("sonarr-4k"), self.settings.key("sonarr-4k"), "v3", self.storage.root("sonarr-4k"), "tv-4k", 30986, True),
            ArrInstance("radarr", "Radarr", "Radarr", self.settings.url("radarr"), self.settings.key("radarr"), "v3", self.storage.root("radarr"), "movies", 30987),
            ArrInstance("radarr-4k", "Radarr 4K", "Radarr", self.settings.url("radarr-4k"), self.settings.key("radarr-4k"), "v3", self.storage.root("radarr-4k"), "movies-4k", 30988, True),
            ArrInstance("lidarr", "Lidarr", "Lidarr", self.settings.url("lidarr"), self.settings.key("lidarr"), "v1", self.storage.root("lidarr"), "music", 30993),
        ]

    def reconcile_async(self):
        if self.runtime.running:
            return False
        threading.Thread(target=self.reconcile, name="reconcile", daemon=True).start()
        return True

    def reconcile(self):
        if not self.runtime.begin():
            return
        self.arrs = self._arr_instances()
        self.runtime.event("Reconciliation started")
        try:
            storage_ok = self._step("setup", self.configure_storage)
            vpn_ok = self._step("privado-vpn", self.check_vpn)
            self._step("flaresolverr", self.check_flaresolverr)
            self._step("qbittorrent", self.configure_qbittorrent, vpn_ok)
            self._step("sabnzbd", self.configure_sabnzbd, vpn_ok)
            if storage_ok:
                for arr in self.arrs:
                    self._step(arr.slug, self.configure_arr, arr)
            else:
                for arr in self.arrs:
                    self.runtime.set(arr.slug, "waiting", "Waiting for writable network media storage")
            self._step("prowlarr", self.configure_prowlarr, vpn_ok)
            self._step("bazarr", self.configure_bazarr, vpn_ok)
            self._step("profilarr", self.configure_profilarr)
            self._step("overseerr", self.configure_overseerr)
            self.runtime.event("Reconciliation completed")
        finally:
            self.runtime.complete()

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
        value = re.sub(r"(?i)(api[_-]?key|password|token)[=:][^&\s\"']+", r"\1=[redacted]", value)
        return value[:300]

    def configure_storage(self):
        roots = [
            Path("/downloads/incomplete"),
            Path("/downloads/complete"),
            *(Path(arr.root) for arr in self.arrs),
        ]
        for root in roots:
            root.mkdir(parents=True, exist_ok=True)
        probe = Path(self.arrs[0].root).parent / ".umbrelarr-write-test"
        probe.write_text("ok")
        probe.unlink()
        return "Download and library roots are writable"

    def save_storage(self, mode, roots):
        snapshot = self.storage.update(mode, roots)
        self.arrs = self._arr_instances()
        self.runtime.event(f"Library roots changed to {mode} storage")
        self.reconcile_async()
        return snapshot

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
        self.client.request("GET", f"{base}/app/version")
        if not vpn_ok:
            return "waiting", "Waiting for a healthy Privado tunnel before applying proxy settings"
        preferences = {
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
        self.client.form("POST", f"{base}/app/setPreferences", {"json": json.dumps(preferences)})
        for category in ("movies", "movies-4k", "tv", "tv-4k", "music"):
            try:
                self.client.form("POST", f"{base}/torrents/createCategory", {"category": category, "savePath": f"/downloads/complete/{category}"})
            except RequestError as error:
                if error.status != 409:
                    raise
        return "Privado SOCKS5, shared paths, and five media categories are configured"

    def configure_sabnzbd(self, vpn_ok):
        url = self.settings.url("sabnzbd")
        key = self.settings.key("sabnzbd")
        if not key:
            raise RuntimeError("SABnzbd API key export is missing")
        self._sab_call(url, key, {"mode": "version"})
        if not vpn_ok:
            return "waiting", "Waiting for a healthy Privado tunnel before applying proxy settings"
        for keyword, value in {
            "socks5_proxy": f"socks5://{self.settings.env.get('UMBREL_ARR_PRIVADO_SOCKS_HOST', 'umbrel-arr-privado-vpn_server_1')}:{self.settings.env.get('UMBREL_ARR_PRIVADO_SOCKS_PORT', '1080')}",
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
        response = self.client.form("POST", f"{url}/api", query)
        if response.body:
            data = response.json()
            if isinstance(data, dict) and data.get("status") is False:
                raise RuntimeError(f"SABnzbd rejected {values.get('mode')}")
        return response

    def configure_arr(self, arr):
        if not arr.api_key:
            raise RuntimeError(f"{arr.name} API key export is missing")
        self.client.json("GET", f"{arr.api}/system/status", arr.api_key)
        self._ensure_root(arr)
        self._ensure_download_client(arr, "QBittorrent", "Umbrel Arr qBittorrent", self.settings.url("qbittorrent"))
        self._ensure_download_client(arr, "Sabnzbd", "Umbrel Arr SABnzbd", self.settings.url("sabnzbd"), self.settings.key("sabnzbd"))
        return f"Root {arr.root} and both {arr.category} download clients are configured"

    def _ensure_root(self, arr):
        existing = self.client.json("GET", f"{arr.api}/rootfolder", arr.api_key)
        if not any(item.get("path", "").rstrip("/") == arr.root.rstrip("/") for item in existing):
            self.client.json("POST", f"{arr.api}/rootfolder", arr.api_key, {"path": arr.root})

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
            raise RuntimeError("Prowlarr API key export is missing")
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
            raise RuntimeError("Bazarr API key export is missing")
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
        self.client.json("GET", f"{url}/api/v1/status")
        databases = self.client.json("GET", f"{url}/api/v1/databases")
        database = next((item for item in databases if item.get("repository_url") == DATABASE_URL or item.get("name") == "Dictionarry"), None)
        if database is None:
            self.client.form("POST", f"{url}/databases/new", {"name": "Dictionarry", "repository_url": DATABASE_URL, "branch": "v2", "sync_strategy": "1440", "auto_pull": "1"})
            return "waiting", "Dictionarry database link queued; waiting for Profilarr to index it"
        instances = self.client.json("GET", f"{url}/api/v1/arr")
        current = {item.get("name"): item for item in instances}
        for arr in self.arrs[:4]:
            if arr.name not in current:
                self.client.form("POST", f"{url}/arr/new", {"name": arr.name, "type": arr.implementation.lower(), "url": arr.url, "external_url": self.settings.external_url(arr.slug), "api_key": arr.api_key, "tags": json.dumps(["4k" if arr.is_4k else "hd", MANAGED_TAG])})
        instances = self.client.json("GET", f"{url}/api/v1/arr")
        current = {item.get("name"): item for item in instances}
        missing = [arr.name for arr in self.arrs[:4] if arr.name not in current]
        if missing:
            return "waiting", f"Waiting for Profilarr Arr connections: {', '.join(missing)}"
        for arr in self.arrs[:4]:
            profiles = UHD_PROFILES if arr.is_4k else HD_PROFILES
            selections = [{"databaseId": database["id"], "profileName": name} for name in profiles]
            instance_id = current[arr.name]["id"]
            self.client.form("POST", f"{url}/arr/{instance_id}/sync?/saveQualityProfiles", {"selections": json.dumps(selections), "priorities": json.dumps([{"databaseId": database["id"], "priority": 1}]), "trigger": "schedule", "cron": "0 3 * * *"}, {"x-sveltekit-action": "true"})
            marker = f"profilarr.initial-sync.{instance_id}"
            if not self.ownership.get(marker):
                try:
                    self.client.form("POST", f"{url}/arr/{instance_id}/sync?/syncQualityProfiles", {}, {"x-sveltekit-action": "true"})
                except RequestError as error:
                    if error.status != 409:
                        raise
                self.ownership.set(marker, True)
        return "Dictionarry profiles and referenced custom formats sync daily to four Arr instances"

    def configure_overseerr(self):
        url = self.settings.url("overseerr")
        key = self.settings.key("overseerr")
        public = self.client.json("GET", f"{url}/api/v1/settings/public")
        if not public.get("initialized"):
            return "action_required", "Complete the Plex sign-in in Overseerr; server registration will continue automatically"
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
            self.reconciler.reconcile()
            self.stop_event.wait(self.reconciler.settings.interval)
