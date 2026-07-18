# umbrelarr

umbrelarr is the stateless management dashboard and idempotent API control
plane for the [Umbrel Arr app store](https://github.com/umbrel-arr/umbrel-app-store).

Users install the apps they want from Umbrel. umbrelarr assembles a selected
set of service modules, detects those installed apps, waits for explicit setup
confirmation, and then reconciles only the settings it owns through service
APIs. A constrained internal broker reads Docker container inventory and
resource statistics for detection and telemetry; the dashboard never receives
the Docker socket and neither process exposes container mutation actions.
umbrelarr never installs containers or creates or edits another app's files.

The matching Umbrel package declares only Prowlarr as its required core
dependency. Its own Umbrel lifecycle export discovers read-only credential
directories for optional installed apps; missing paths resolve to `/dev/null`,
so absent services are detected without Docker creating phantom app
directories.

## Modular stacks

The module catalog in `app/catalog.py` describes service identity, role,
credentials, and legacy migration selection. Dependencies are derived from the enabled
modules instead of a fixed stack. Prowlarr and umbrelarr are the small required
core because Prowlarr tags are the API-owned persistence layer for consent,
module selection, VPN provider choice, and library layout.

The Services page is the single service-management workflow. Its fleet cards
come only from Docker-discovered containers or explicit direct connections;
catalog defaults are never presented as local services. Docker-discovered apps
that are not managed yet remain visible with one **Add service** action, and a
removed app returns to that available state without being uninstalled. Jellyfin
and Plex remain opt-in modules that connect to
the official apps the operator already installed; neither is silently added to
an existing stack.

VPN routing is provided through adapters in `app/vpn.py`. The built-in choices
are:

- `privado`: the existing managed Privado app, including credential handoff and
  WireGuard/SOCKS5 health.
- `generic-socks5`: an externally managed VPN provider that exposes SOCKS5;
  set `UMBREL_ARR_SOCKS5_HOST` and optionally `UMBREL_ARR_SOCKS5_PORT`.
- `direct`: no VPN proxy. Umbrelarr clears the proxy fields it owns while
  preserving unrelated service settings.

New providers implement the small `VpnProvider` contract rather than adding
provider branches throughout the reconciler. `UMBREL_ARR_VPN_PROVIDER` and
`UMBREL_ARR_ENABLED_SERVICES` provide deployment defaults; confirmed UI choices
are restored from Prowlarr API markers. Existing 1.1 installations without the
new markers retain the complete Privado-backed stack.

## Explicit setup

On first launch, open **Services** and choose **Add service**. Prowlarr is the
only required service; every other app starts unselected. Add the app cards that
match software already installed on the Umbrel. Privado is an ordinary optional
service card—there is no separate routing or starting-profile step.

**Review changes** performs read-only reachability and credential validation for
exactly that selection. It reports missing apps, missing or rejected API keys,
media-server sign-in requirements, and qBittorrent's one-time-password handoff
before **Apply changes** is enabled. Active service cards do not change during
review, and a failed later addition leaves the existing fleet active. Library
locations are configured separately from each library's page after connection.

On any Docker host, Docker inventory is authoritative for whether a supported app is
installed, stopped, or running. Running containers are then checked through
their service-native APIs, because a running container alone does not prove
that its API is ready or its credentials are valid. The broker publishes only
allowlisted, sanitized inventory plus CPU, memory, disk-I/O, and network-I/O
statistics. It recognizes only exact supported-service matches from its
explicit `io.umbrelarr.service` label, standard Compose service/project labels,
image repository name, or container name; unrelated containers and Umbrel app
sidecars are ignored. Resource samples retain their timestamp so stale or unavailable
telemetry is never presented as healthy or zero usage. CPU follows Docker's
per-logical-CPU convention (so a container using two full cores reports 200%);
the dashboard scales that value against the host's reported online CPU count.
Memory uses Docker's Linux working-set convention and excludes inactive cache.
The broker defaults to loopback and refuses any non-loopback bind unless a
bearer token is configured; the Umbrel package shares that token only with the
unprivileged dashboard container.

Upgrades from 1.1 also accept the manager-owned deterministic password that the
old dependency export could assign to qBittorrent, then immediately rotate the
Web UI to qBittorrent's own Umbrel-derived password.

If an optional service is installed after umbrelarr has already started, restart
umbrelarr once so Umbrel can refresh the read-only credential mounts, then run
detection again. The dashboard calls this out when an installed app is reachable
but its API key handoff is not yet mounted.

Jellyfin requires an API key named `umbrelarr`; umbrelarr deliberately ignores
every other Jellyfin API key. Plex must already be claimed or signed in. The
official apps' config directories are mounted read-only so umbrelarr can obtain
that one named key or the existing Plex token, while all library changes go
through the corresponding media-server API.

Consent, storage selection, and the Profilarr initial-sync marker are restored
from umbrelarr-owned Prowlarr tags. API keys may be read from app-generated
configuration mounted read-only at `/managed-config`; they are never copied,
displayed, logged, or persisted by umbrelarr.

## Storage contract

- `local` uses the five `/downloads` presets.
- `network` uses the five `/network` presets.
- `adopt` accepts one existing root-folder ID from each Arr API.
- `custom` browses folders reported by a managed Arr API and accepts a path only
  when every managed media service reports that exact mount.

Existing roots and settings not owned by umbrelarr are preserved. Ambiguous
existing roots require an explicit selection and are persisted by API marker.

## Managed ownership

umbrelarr continuously reconciles only these declared resources:

| Module | API-owned settings |
| --- | --- |
| VPN adapter | Provider health, optional login handoff, and the selected SOCKS5 endpoint |
| qBittorrent / SABnzbd | Proxy fields, shared download paths, and categories for selected media modules |
| Sonarr / Radarr / Lidarr | Selected root, enabled download clients, and the stable Umbrel Arr connection names |
| Prowlarr | Selected proxy fields, selected Arr applications, FlareSolverr integration, and Umbrel Arr state tags |
| Bazarr | Selected Sonarr/Radarr connections and provider proxy fields |
| Profilarr / Overseerr | Stable Umbrel Arr server registrations and initial synchronization |
| Jellyfin / Plex | Stable `Umbrel Arr …` libraries and their selected Arr root paths |

Unrelated media libraries, indexers, providers, categories, roots, profiles,
servers, and user preferences are preserved. A Plex library that already uses
an `Umbrel Arr …` name with a different path is reported for explicit action
instead of being overwritten.

## Development

The runtime uses only the Python standard library and does not need writable
state. Run the mandatory checks with:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q app tests
```

Browser acceptance tests use pinned Playwright and run in Chromium on GitHub's
Linux runner at desktop and narrow widths. To run them on a Linux workstation:

```sh
npm ci
npx playwright install --with-deps chromium
npm run test:browser
```

Run the dashboard locally with:

```sh
UMBREL_ARR_BASE_URL=http://localhost PORT=8080 python3 app/app.py
```

`UMBREL_ARR_BASE_URL` is the public HTTP or HTTPS origin used to build default
service links. It must not include a port or path because each supported app has
its own public port. Use `http://localhost` for local iteration and
`http://umbrel.local` on Umbrel. `DEVICE_DOMAIN_NAME` remains a compatibility
fallback when the base URL is unset. A service-specific
`UMBREL_ARR_<SERVICE>_URL` still takes priority when umbrelarr must reach that
service through a private container address.

Without a configured Docker broker, the Services page labels its scope
**Direct** and shows only the running umbrelarr process plus services that have
an explicit connection; catalog defaults are not described as local
containers. Use the Add service modal to enter a direct service URL and choose
the service to manage. Prowlarr, Sonarr, Radarr, Lidarr, SABnzbd, Bazarr, and
Overseerr generate their own API keys; when the matching read-only managed
configuration is available, umbrelarr adopts and validates that key during the
service check and reports **Connected automatically** without returning it to
the browser.

If automatic discovery is unavailable or the key is rejected, choose **Enter
in UI** for a write-only key retained in memory by the running process, or
**Environment variable** for restart-safe configuration. The modal shows the
exact `UMBREL_ARR_*_API_KEY` name for the selected service. An invalid
environment key must be replaced or removed and the process restarted because
environment configuration keeps precedence over managed configuration.

Jellyfin has an explicit one-time **Create and connect** action. The selected
Jellyfin address is resolved server-side; an administrator username and
password are sent directly to that instance, used to reuse or create the one
Jellyfin-owned API key named `umbrelarr`, and then discarded after the temporary
administrator session is logged out. The dedicated API key remains in runtime
memory and is never returned by the setup API. Jellyfin continues to own the
durable key. Plex keeps its token/claim flow, Overseerr keeps its Plex sign-in
flow, and qBittorrent keeps its one-time-password flow.

The setup completes without redirecting to another dashboard. Set the matching
`UMBREL_ARR_*_URL` when the service address also needs to survive a restart.
Container builds and
integration validation run only on GitHub's Linux runners, never through Docker
or OrbStack on macOS.
