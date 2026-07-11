# umbrelarr

umbrelarr is the management dashboard and idempotent configuration service for
the [Umbrel Arr app store](https://github.com/umbrel-arr/umbrel-app-store).

It monitors the media stack, forwards the one-time Privado login, manages
service-to-service registrations, and keeps library roots consistent across
Sonarr, Radarr, Lidarr, Prowlarr, Bazarr, Profilarr, and Overseerr.

## Storage contract

- `/downloads` is Umbrel shared storage. The default roots match the official
  Umbrel media layout: `/downloads/movies`, `/downloads/shows`, and
  `/downloads/music` with separate `-4k` roots.
- `/network` is linked network storage. The dashboard can switch all managed
  roots to `/network` presets or save explicit paths beneath that mount.
- `/data` stores umbrelarr state and owned-resource metadata.

## Development

The runtime uses only the Python standard library.

```sh
python3 -m unittest discover -s tests -v
PORT=8080 STATE_DIR=/tmp/umbrelarr-state python3 app/app.py
```

Container builds are intentionally restricted to Linux CI for this project.
