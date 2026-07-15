import threading


LOCAL_ROOTS = {
    "sonarr": "/downloads/shows",
    "sonarr-4k": "/downloads/shows-4k",
    "radarr": "/downloads/movies",
    "radarr-4k": "/downloads/movies-4k",
    "lidarr": "/downloads/music",
}

NETWORK_ROOTS = {
    "sonarr": "/network/shows",
    "sonarr-4k": "/network/shows-4k",
    "radarr": "/network/movies",
    "radarr-4k": "/network/movies-4k",
    "lidarr": "/network/music",
}

PRESETS = {"local": LOCAL_ROOTS, "network": NETWORK_ROOTS}

LIBRARY_DEFINITIONS = {
    "sonarr": {
        "id": "tv",
        "name": "TV",
        "variant": "HD",
        "category": "tv",
        "apps": ["sonarr", "qbittorrent", "sabnzbd", "prowlarr", "bazarr", "profilarr", "overseerr", "jellyfin", "plex"],
    },
    "sonarr-4k": {
        "id": "tv-4k",
        "name": "TV",
        "variant": "4K",
        "category": "tv-4k",
        "apps": ["sonarr-4k", "qbittorrent", "sabnzbd", "prowlarr", "profilarr", "overseerr", "jellyfin", "plex"],
    },
    "radarr": {
        "id": "movies",
        "name": "Movies",
        "variant": "HD",
        "category": "movies",
        "apps": ["radarr", "qbittorrent", "sabnzbd", "prowlarr", "bazarr", "profilarr", "overseerr", "jellyfin", "plex"],
    },
    "radarr-4k": {
        "id": "movies-4k",
        "name": "Movies",
        "variant": "4K",
        "category": "movies-4k",
        "apps": ["radarr-4k", "qbittorrent", "sabnzbd", "prowlarr", "profilarr", "overseerr", "jellyfin", "plex"],
    },
    "lidarr": {
        "id": "music",
        "name": "Music",
        "variant": "Standard",
        "category": "music",
        "apps": ["lidarr", "qbittorrent", "sabnzbd", "prowlarr", "jellyfin", "plex"],
    },
}


class StorageSettings:
    """In-memory view derived from the Arr root-folder APIs.

    Selection is persisted by API-owned Prowlarr tags, never by local files.
    The roots and candidates in this object are only a cache of the latest API
    read and are safe to discard on every restart.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.enabled_modules = set(LIBRARY_DEFINITIONS)
        self.data = {
            "mode": "local",
            "roots": dict(LOCAL_ROOTS),
            "rootIds": {},
            "candidates": {slug: [] for slug in LOCAL_ROOTS},
            "actionRequired": False,
        }

    def set_enabled_modules(self, enabled):
        with self._lock:
            self.enabled_modules = set(enabled)

    def root(self, slug):
        with self._lock:
            return self.data["roots"].get(slug, LOCAL_ROOTS[slug])

    def update_from_apis(self, folders, mode=None, root_ids=None):
        root_ids = {slug: int(value) for slug, value in (root_ids or {}).items()}
        enabled = tuple(slug for slug in LOCAL_ROOTS if slug in self.enabled_modules)
        candidates = {
            slug: [
                {"id": int(item["id"]), "path": str(item.get("path", "")).rstrip("/") or "/"}
                for item in folders.get(slug, [])
                if item.get("id") is not None and item.get("path")
            ]
            for slug in enabled
        }
        selected_ids = {}
        roots = {}
        action_required = False

        if mode in PRESETS:
            roots = {slug: PRESETS[mode][slug] for slug in enabled}
            for slug, path in roots.items():
                match = next((item for item in candidates[slug] if item["path"] == path), None)
                if match:
                    selected_ids[slug] = match["id"]
        elif mode == "adopted":
            for slug in enabled:
                match = next((item for item in candidates[slug] if item["id"] == root_ids.get(slug)), None)
                if match is None:
                    action_required = True
                    continue
                roots[slug] = match["path"]
                selected_ids[slug] = match["id"]
        else:
            preset_matches = []
            for preset_name, preset in PRESETS.items():
                matches = {
                    slug: next((item for item in candidates[slug] if item["path"] == path), None)
                    for slug, path in preset.items() if slug in enabled
                }
                if all(matches.values()):
                    preset_matches.append((preset_name, preset, matches))
            if len(preset_matches) == 1:
                mode, preset, matches = preset_matches[0]
                roots = dict(preset)
                selected_ids = {slug: item["id"] for slug, item in matches.items()}
            else:
                mode = "adopted"
                for slug, values in candidates.items():
                    if len(values) == 1:
                        roots[slug] = values[0]["path"]
                        selected_ids[slug] = values[0]["id"]
                    else:
                        action_required = True

        if set(roots) != set(enabled):
            action_required = True
            for slug in enabled:
                roots.setdefault(slug, LOCAL_ROOTS[slug])
        with self._lock:
            self.data = {
                "mode": mode,
                "roots": roots,
                "rootIds": selected_ids,
                "candidates": candidates,
                "actionRequired": action_required,
            }
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            return {
                "mode": self.data["mode"],
                "roots": dict(self.data["roots"]),
                "rootIds": dict(self.data["rootIds"]),
                "candidates": {
                    slug: [dict(item) for item in values]
                    for slug, values in self.data["candidates"].items()
                },
                "actionRequired": self.data["actionRequired"],
                "presets": {
                    name: {slug: path for slug, path in values.items() if slug in self.enabled_modules}
                    for name, values in PRESETS.items()
                },
                "libraries": [
                    {
                        "key": key,
                        "root": self.data["roots"][key],
                        **definition,
                        "apps": [slug for slug in definition["apps"] if slug in self.enabled_modules],
                    }
                    for key, definition in LIBRARY_DEFINITIONS.items()
                    if key in self.enabled_modules
                ],
            }
