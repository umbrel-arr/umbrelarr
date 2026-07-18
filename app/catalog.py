from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ServiceModule:
    id: str
    name: str
    port: int
    role: str
    requires_api_key: bool = False
    required: bool = False
    default_enabled: bool = True
    credential_setup: str = "none"

    def public(self):
        value = asdict(self)
        value["credentialSetup"] = value.pop("credential_setup")
        return value


SERVICE_MODULES = (
    ServiceModule("umbrelarr", "umbrelarr", 30992, "control_plane", required=True),
    # Prowlarr remains the small API-owned state anchor. Umbrelarr stores consent,
    # selected modules, provider choice, and storage markers as Prowlarr tags.
    ServiceModule(
        "prowlarr", "Prowlarr", 30982, "indexer_manager", True, True,
        credential_setup="generated",
    ),
    ServiceModule("privado-vpn", "Privado VPN", 30980, "vpn_provider"),
    ServiceModule("flaresolverr", "FlareSolverr", 30981, "challenge_solver"),
    ServiceModule("qbittorrent", "qBittorrent", 30983, "download_client"),
    ServiceModule(
        "sabnzbd", "SABnzbd", 30984, "download_client", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "sonarr", "Sonarr", 30985, "media_manager", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "sonarr-4k", "Sonarr 4K", 30986, "media_manager", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "radarr", "Radarr", 30987, "media_manager", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "radarr-4k", "Radarr 4K", 30988, "media_manager", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "lidarr", "Lidarr", 30993, "media_manager", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "bazarr", "Bazarr", 30989, "subtitle_manager", True,
        credential_setup="generated",
    ),
    ServiceModule(
        "overseerr", "Overseerr", 30990, "request_manager", True,
        credential_setup="generated",
    ),
    ServiceModule("profilarr", "Profilarr", 30991, "profile_manager"),
    # Media servers are user-installed official Umbrel apps. Umbrelarr only
    # discovers and configures them when they are explicitly selected.
    ServiceModule(
        "jellyfin", "Jellyfin", 8096, "media_server", True,
        default_enabled=False, credential_setup="jellyfin_admin",
    ),
    ServiceModule(
        "plex", "Plex", 32400, "media_server", True,
        default_enabled=False, credential_setup="existing_token",
    ),
)

MODULES = {module.id: module for module in SERVICE_MODULES}
CORE_MODULES = frozenset(module.id for module in SERVICE_MODULES if module.required)
DEFAULT_MODULES = frozenset(module.id for module in SERVICE_MODULES if module.default_enabled)
MEDIA_MODULES = tuple(module.id for module in SERVICE_MODULES if module.role == "media_manager")
VIDEO_MODULES = tuple(slug for slug in MEDIA_MODULES if slug != "lidarr")
MEDIA_SERVER_MODULES = tuple(module.id for module in SERVICE_MODULES if module.role == "media_server")

def normalize_modules(values):
    selected = {str(value).strip() for value in values if str(value).strip() in MODULES}
    return frozenset(selected | CORE_MODULES)


def dependencies_for(enabled, vpn_service_id=None):
    enabled = normalize_modules(enabled)
    vpn_dependency = (vpn_service_id,) if vpn_service_id in enabled else ()
    downloads = tuple(slug for slug in ("qbittorrent", "sabnzbd") if slug in enabled)
    media = tuple(slug for slug in MEDIA_MODULES if slug in enabled)
    video = tuple(slug for slug in VIDEO_MODULES if slug in enabled)
    dependencies = {slug: () for slug in enabled}
    dependencies["umbrelarr"] = ()
    dependencies["prowlarr"] = (
        *vpn_dependency,
        *(("flaresolverr",) if "flaresolverr" in enabled else ()),
        *media,
    )
    if "flaresolverr" in enabled:
        dependencies["flaresolverr"] = vpn_dependency
    for slug in downloads:
        dependencies[slug] = vpn_dependency
    for slug in media:
        dependencies[slug] = ("umbrelarr", *downloads)
    if "bazarr" in enabled:
        dependencies["bazarr"] = (*vpn_dependency, *(slug for slug in ("sonarr", "radarr") if slug in enabled))
    if "profilarr" in enabled:
        dependencies["profilarr"] = video
    if "overseerr" in enabled:
        dependencies["overseerr"] = video
    for slug in MEDIA_SERVER_MODULES:
        if slug in enabled:
            dependencies[slug] = ("umbrelarr", *media)
    return dependencies


def validate_modules(enabled):
    enabled = normalize_modules(enabled)
    errors = []
    if "bazarr" in enabled and not ({"sonarr", "radarr"} <= enabled):
        errors.append("Bazarr requires Sonarr and Radarr")
    if "profilarr" in enabled and not any(slug in enabled for slug in VIDEO_MODULES):
        errors.append("Profilarr requires at least one Sonarr or Radarr module")
    if "overseerr" in enabled and not any(slug in enabled for slug in VIDEO_MODULES):
        errors.append("Overseerr requires at least one Sonarr or Radarr module")
    for slug in MEDIA_SERVER_MODULES:
        if slug in enabled and not any(module in enabled for module in MEDIA_MODULES):
            errors.append(f"{MODULES[slug].name} requires at least one Sonarr, Radarr, or Lidarr module")
    return errors
