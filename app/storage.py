import json
import threading
from pathlib import Path, PurePosixPath


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


class StorageSettings:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data = self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {}
        mode = data.get("mode", "local")
        if mode not in PRESETS:
            mode = "local"
        roots = dict(PRESETS[mode])
        for slug, value in data.get("roots", {}).items():
            if slug in roots:
                try:
                    roots[slug] = self._validate_path(value)
                except ValueError:
                    pass
        return {"mode": mode, "roots": roots}

    @staticmethod
    def _validate_path(value):
        value = str(value).strip().rstrip("/") or "/"
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("Library paths must be absolute and cannot contain '..'")
        if path.parts[:2] not in {("/", "downloads"), ("/", "network")}:
            raise ValueError("Library paths must start with /downloads or /network")
        return str(path)

    def root(self, slug):
        with self._lock:
            return self.data["roots"][slug]

    def update(self, mode, roots):
        if mode not in PRESETS:
            raise ValueError("Storage mode must be local or network")
        values = {}
        for slug in PRESETS[mode]:
            values[slug] = self._validate_path(roots.get(slug, PRESETS[mode][slug]))
        with self._lock:
            self.data = {"mode": mode, "roots": values}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n")
            temporary.replace(self.path)
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            return {
                "mode": self.data["mode"],
                "roots": dict(self.data["roots"]),
                "presets": {name: dict(values) for name, values in PRESETS.items()},
            }
