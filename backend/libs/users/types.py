from enum import StrEnum


class ClientIpSourceType(StrEnum):
    """Which proxies stand in front of the API, and so where the client's IP comes from."""

    # Nothing in front: the connection's own address, as in local development
    CONNECTION = "CONNECTION"
    # Railway's edge, which sets X-Real-IP to the address that connected to it
    RAILWAY = "RAILWAY"
    # Cloudflare in front of Railway's edge, which sets CF-Connecting-IP
    CLOUDFLARE = "CLOUDFLARE"
