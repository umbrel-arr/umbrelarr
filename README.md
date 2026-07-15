# umbrelarr

umbrelarr is the stateless management dashboard and idempotent API control
plane for the [Umbrel Arr app store](https://github.com/umbrel-arr/umbrel-app-store).

Users install the apps they want from Umbrel. umbrelarr assembles a selected
set of service modules, detects those installed apps, waits for explicit setup
confirmation, and then reconciles only the settings it owns through service
APIs. It never installs or controls containers and never creates or edits
another app's files.

The matching Umbrel package declares only Prowlarr as its required core
dependency. Its own Umbrel lifecycle export discovers read-only credential
directories for optional installed apps; missing paths resolve to `/dev/null`,
so absent services are detected without Docker creating phantom app
directories.

## Modular stacks

The module catalog in `app/catalog.py` describes service identity, role,
credentials, and default selection. Dependencies are derived from the enabled
modules instead of a fixed stack. Prowlarr and umbrelarr are the small required
core because Prowlarr tags are the API-owned persistence layer for consent,
module selection, VPN provider choice, and library layout.

The setup screen provides core-only, TV/torrent, video/Usenet, and complete
starting profiles. Profiles are shortcuts over the same module catalog, so the
operator can still adjust every service independently and choose VPN routing
separately.

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

On first launch, open **Setup**, choose service modules and a VPN provider, then
run detection. Detection performs read-only health and credential discovery for
only that selection. Review every app, choose local, network, or existing
API-reported library roots, provide qBittorrent's one-time password if requested,
and confirm before any managed API mutation occurs.

If an optional service is installed after umbrelarr has already started, restart
umbrelarr once so Umbrel can refresh the read-only credential mounts, then run
detection again. The dashboard calls this out when an installed app is reachable
but its API key handoff is not yet mounted.

Consent, storage selection, and the Profilarr initial-sync marker are restored
from umbrelarr-owned Prowlarr tags. API keys may be read from app-generated
configuration mounted read-only at `/managed-config`; they are never copied,
displayed, logged, or persisted by umbrelarr.

## Storage contract

- `local` uses the five `/downloads` presets.
- `network` uses the five `/network` presets.
- `adopt` accepts one existing root-folder ID from each Arr API.
- Arbitrary paths are intentionally unsupported; use API-reported existing
  roots when a library does not fit a preset.

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

Unrelated indexers, providers, categories, roots, profiles, servers, and user
preferences are preserved.

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

Run the dashboard directly with `PORT=8080 python3 app/app.py`. Supply service
URLs and optional API-key overrides through the `UMBREL_ARR_*` environment
variables. Container builds and integration validation run only on GitHub's
Linux runners, never through Docker or OrbStack on macOS.
