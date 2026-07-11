import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


VALID_STATES = {"unknown", "waiting", "action_required", "configuring", "healthy", "failed"}


@dataclass
class ServiceStatus:
    id: str
    name: str
    status: str = "unknown"
    detail: str = "Waiting for the first check"
    link: str = ""
    checked_at: int = 0


class RuntimeState:
    def __init__(self, services):
        self._lock = threading.RLock()
        self.services = {service.id: service for service in services}
        self.running = False
        self.last_started_at = 0
        self.last_completed_at = 0
        self.events = []

    def set(self, service_id, status, detail):
        if status not in VALID_STATES:
            raise ValueError(status)
        with self._lock:
            service = self.services[service_id]
            service.status = status
            service.detail = detail
            service.checked_at = int(time.time())

    def event(self, message, level="info"):
        with self._lock:
            self.events.insert(0, {"at": int(time.time()), "level": level, "message": message})
            del self.events[50:]

    def begin(self):
        with self._lock:
            if self.running:
                return False
            self.running = True
            self.last_started_at = int(time.time())
            return True

    def complete(self):
        with self._lock:
            self.running = False
            self.last_completed_at = int(time.time())

    def snapshot(self):
        with self._lock:
            values = list(self.services.values())
            counts = {state: 0 for state in VALID_STATES}
            for service in values:
                counts[service.status] += 1
            return {
                "running": self.running,
                "lastStartedAt": self.last_started_at,
                "lastCompletedAt": self.last_completed_at,
                "counts": counts,
                "services": [asdict(service) for service in values],
                "events": list(self.events),
            }


class OwnershipState:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.data = {}
        try:
            self.data = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.data = {}

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default)

    def set(self, key, value):
        with self._lock:
            self.data[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n")
            temporary.replace(self.path)
