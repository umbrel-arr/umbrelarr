# umbrelarr

umbrelarr is the stateless management dashboard and idempotent API control
plane for the [Umbrel Arr app store](https://github.com/umbrel-arr/umbrel-app-store).

Users install the 13 prerequisite apps from Umbrel. umbrelarr detects those
installed apps, waits for an explicit setup confirmation, and then reconciles
only the settings it owns through service APIs. It never installs or controls
containers and never creates or edits another app's files.

## Explicit setup

On first launch, open **Setup** and run detection. Detection performs read-only
health and credential discovery. Review every app, choose local, network, or
existing API-reported library roots, provide qBittorrent's one-time password if
requested, and confirm before any managed API mutation occurs.

Consent, storage selection, and the Profilarr initial-sync marker are restored
from umbrelarr-owned Prowlarr tags. API keys may be read from app-generated
configuration mounted read-only at `/managed-config`; they are never copied,
displayed, logged, or persisted by umbrelarr.

## Storage contract

- `local` uses the five `/downloads` presets.
- `network` uses the five `/network` presets.
- `adopt` accepts one existing root-folder ID from each Arr API.
- Arbitrary paths are intentionally unsupported in 1.1.

Existing roots and settings not owned by umbrelarr are preserved. Ambiguous
existing roots require an explicit selection and are persisted by API marker.

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
