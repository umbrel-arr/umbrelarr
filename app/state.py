import copy
import threading
import time
from dataclasses import asdict, dataclass, field


VALID_STATES = {"unknown", "waiting", "action_required", "configuring", "healthy", "failed"}


@dataclass
class ServiceStatus:
    id: str
    name: str
    role: str = ""
    status: str = "unknown"
    detail: str = "Waiting for the first check"
    link: str = ""
    checked_at: int = 0
    checks: list = field(default_factory=list)
    container: dict = field(default_factory=dict)
    resources: dict = field(default_factory=dict)


class RuntimeState:
    def __init__(self, services, dependencies=None):
        self._lock = threading.RLock()
        self.services = {service.id: service for service in services}
        self.dependencies = {
            service_id: tuple(upstream)
            for service_id, upstream in (dependencies or {}).items()
        }
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
            service.checks.append({"at": service.checked_at, "status": status})
            del service.checks[:-24]

    def set_unchecked(self, service_id, status, detail):
        """Describe a preflight state without pretending a health check ran."""
        if status not in VALID_STATES:
            raise ValueError(status)
        with self._lock:
            service = self.services[service_id]
            service.status = status
            service.detail = detail
            service.checked_at = 0
            service.checks.clear()

    def set_resources(self, service_id, resources):
        """Store a resource snapshot supplied by the constrained host integration."""
        with self._lock:
            self.services[service_id].resources = copy.deepcopy(resources or {})

    def retain_resources(self, service_id, source="docker"):
        """Keep the last measured values without advancing their sample timestamp."""
        with self._lock:
            current = copy.deepcopy(self.services[service_id].resources)
            has_sample = bool(current.get("updatedAt")) and any(
                current.get(key) not in (None, {})
                for key in ("cpu", "memory", "blockIo", "network")
            )
            if has_sample:
                current["sampleState"] = "last_sample"
                self.services[service_id].resources = current
            else:
                self.services[service_id].resources = {
                    "source": source,
                    "sampleState": "unavailable",
                }

    def set_container(self, service_id, container):
        """Store sanitized Docker runtime metadata for one managed service."""
        with self._lock:
            self.services[service_id].container = dict(container or {})

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
            services = []
            for service in values:
                value = asdict(service)
                upstream = self.dependencies.get(service.id, ())
                value["dependencies"] = list(upstream)
                value["waitingOn"] = [
                    service_id
                    for service_id in upstream
                    if self.services[service_id].status != "healthy"
                ]
                services.append(value)
            return {
                "running": self.running,
                "lastStartedAt": self.last_started_at,
                "lastCompletedAt": self.last_completed_at,
                "counts": counts,
                "services": services,
                "events": list(self.events),
            }
