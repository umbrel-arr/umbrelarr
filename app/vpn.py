from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProxySettings:
    host: str
    port: int


@dataclass(frozen=True)
class VpnProvider:
    id: str
    name: str
    description: str
    service_id: str | None = None
    supports_login: bool = False

    def public(self):
        return asdict(self)

    def proxy(self, settings):
        return None

    def check(self, settings, client):
        return "healthy", "Direct connection selected; no VPN proxy is managed"

    def save_login(self, settings, client, username, password):
        raise ValueError(f"{self.name} does not accept credentials through umbrelarr")


class PrivadoProvider(VpnProvider):
    def __init__(self):
        super().__init__(
            "privado", "Privado VPN",
            "Routes supported network clients through the managed Privado WireGuard and SOCKS5 app.",
            "privado-vpn", True,
        )

    def proxy(self, settings):
        return ProxySettings(
            settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_HOST", "umbrel-arr-privado-vpn_server_1"),
            int(settings.env.get("UMBREL_ARR_PRIVADO_SOCKS_PORT", "1080")),
        )

    def check(self, settings, client):
        status = client.json("GET", f"{settings.url(self.service_id)}/api/status")
        if status.get("state") == "healthy":
            public_ip = status.get("publicIp")
            route = public_ip if public_ip and public_ip != "unknown" else status.get("server")
            return "healthy", f"WireGuard and SOCKS5 are healthy via {route or 'private exit'}"
        if not status.get("credentialsConfigured"):
            return "action_required", "Enter your Privado login to start the tunnel"
        return "waiting", f"Privado is {status.get('state', 'starting')}; waiting for WireGuard and SOCKS5"

    def save_login(self, settings, client, username, password):
        if not username.strip() or not password:
            raise ValueError("Privado username and password are required")
        client.form(
            "POST",
            f"{settings.url(self.service_id)}/setup",
            {"username": username.strip(), "password": password},
        )


class GenericSocksProvider(VpnProvider):
    def __init__(self):
        super().__init__(
            "generic-socks5", "Generic SOCKS5",
            "Uses an externally managed SOCKS5 endpoint; umbrelarr does not own the tunnel.",
        )

    def proxy(self, settings):
        host = settings.env.get("UMBREL_ARR_SOCKS5_HOST", "").strip()
        port = int(settings.env.get("UMBREL_ARR_SOCKS5_PORT", "1080"))
        return ProxySettings(host, port) if host else None

    def check(self, settings, client):
        proxy = self.proxy(settings)
        if proxy is None:
            return "action_required", "Set UMBREL_ARR_SOCKS5_HOST for the selected SOCKS5 provider"
        client.tcp(proxy.host, proxy.port, timeout=3)
        return "healthy", f"Selected SOCKS5 endpoint is reachable at {proxy.host}:{proxy.port}"


VPN_PROVIDERS = {
    provider.id: provider
    for provider in (
        PrivadoProvider(),
        GenericSocksProvider(),
        VpnProvider(
            "direct", "No VPN",
            "Clears proxy fields owned by umbrelarr; downloader traffic leaves directly.",
        ),
    )
}


def get_vpn_provider(provider_id):
    try:
        return VPN_PROVIDERS[provider_id]
    except KeyError as error:
        raise ValueError(f"Unknown VPN provider: {provider_id}") from error
