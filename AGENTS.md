# umbrelarr Development Guide

umbrelarr is the control plane and management dashboard for the Umbrel Arr
community app store.

## Repository rules

- Always sign commits.
- Use meaningful branches such as `feat/storage-settings` or
  `fix/reconcile-prowlarr`.
- Never commit credentials, API keys, private hostnames, or machine paths.
- Keep all managed changes idempotent and preserve settings not owned by
  umbrelarr.
- Pin the base image and publish multi-architecture images by immutable digest.
- Do not run Docker or OrbStack on macOS. Container builds and image validation
  belong on GitHub's Linux runners.

## Validation

Run before publishing:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q app tests
```

Dashboard changes must cover loading, unknown, waiting, action-required,
healthy, and failed service states at desktop and narrow widths.
