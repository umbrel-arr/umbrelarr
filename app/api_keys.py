import json
import re
from pathlib import Path
from xml.etree import ElementTree


SOURCES = {
    "prowlarr": ("xml", "prowlarr/config.xml"),
    "sonarr": ("xml", "sonarr/config.xml"),
    "sonarr-4k": ("xml", "sonarr-4k/config.xml"),
    "radarr": ("xml", "radarr/config.xml"),
    "radarr-4k": ("xml", "radarr-4k/config.xml"),
    "lidarr": ("xml", "lidarr/config.xml"),
    "sabnzbd": ("ini", "sabnzbd/sabnzbd.ini"),
    "bazarr": ("yaml", "bazarr/config/config.yaml"),
    "overseerr": ("json", "overseerr/settings.json"),
}


class ApiKeyResolver:
    """Reads app-generated API keys from read-only managed config volumes."""

    def __init__(self, root="/managed-config"):
        self.root = Path(root)

    def resolve(self, slug):
        source = SOURCES.get(slug)
        if source is None:
            return ""
        kind, relative_path = source
        path = self.root / relative_path
        try:
            value = getattr(self, f"_{kind}")(path)
        except (OSError, ValueError, ElementTree.ParseError, json.JSONDecodeError):
            return ""
        return self._clean(value)

    @staticmethod
    def _clean(value):
        if not isinstance(value, str):
            return ""
        value = value.strip()
        if not value or value.casefold() in {"none", "null"}:
            return ""
        if len(value) > 512 or any(character.isspace() for character in value):
            return ""
        return value

    @staticmethod
    def _xml(path):
        root = ElementTree.parse(path).getroot()
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].casefold() == "apikey":
                return element.text or ""
        return ""

    @staticmethod
    def _ini(path):
        # SABnzbd writes an `__encoding__` preamble before its first section,
        # which deliberately is not accepted by Python's ConfigParser.
        match = re.search(
            r"(?im)^\s*api_key\s*=\s*([^\s#;]+)",
            path.read_text(encoding="utf-8"),
        )
        return match.group(1) if match else ""

    @staticmethod
    def _yaml(path):
        # Bazarr's generated file has a stable two-level `auth.apikey` shape.
        # A targeted reader avoids adding a YAML dependency to the runtime.
        in_auth = False
        auth_indent = -1
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            if re.fullmatch(r"auth\s*:\s*(?:#.*)?", stripped, re.IGNORECASE):
                in_auth = True
                auth_indent = indent
                continue
            if in_auth and indent <= auth_indent:
                in_auth = False
            if not in_auth:
                continue
            match = re.match(r"apikey\s*:\s*(.*?)\s*(?:#.*)?$", stripped, re.IGNORECASE)
            if match:
                return match.group(1).strip().strip("\"'")
        return ""

    @staticmethod
    def _json(path):
        data = json.loads(path.read_text(encoding="utf-8"))
        main = data.get("main", {}) if isinstance(data, dict) else {}
        return main.get("apiKey", "") if isinstance(main, dict) else ""
