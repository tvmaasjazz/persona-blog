from collections.abc import Callable
from ipaddress import IPv4Address, IPv6Address, ip_address

from libs.users.constants import CLOUDFLARE_IP_NETWORKS
from libs.users.types import ClientIpSourceType


class ClientIpUtils:
    """Picks the client's IP from the connection and the proxies' headers; static methods
    only."""

    @staticmethod
    def resolve_client_ip(
        client_ip_source: ClientIpSourceType,
        connection_ip: str | None,
        real_ip: str | None,
        cloudflare_connecting_ip: str | None,
    ) -> str | None:
        """Returns the client's IP for the proxies in front of the API, or None when nothing
        names one."""
        resolve_client_ip_for_source = CLIENT_IP_RESOLVER_BY_SOURCE_TYPE.get(client_ip_source)
        if resolve_client_ip_for_source is None:
            raise NotImplementedError(f"No client IP resolver for {client_ip_source}")
        return resolve_client_ip_for_source(connection_ip, real_ip, cloudflare_connecting_ip)

    @staticmethod
    def _resolve_connection_client_ip(
        connection_ip: str | None, real_ip: str | None, cloudflare_connecting_ip: str | None
    ) -> str | None:
        # Nothing in front, so a header is whatever the client sent
        return connection_ip

    @staticmethod
    def _resolve_railway_client_ip(
        connection_ip: str | None, real_ip: str | None, cloudflare_connecting_ip: str | None
    ) -> str | None:
        return real_ip or connection_ip

    @staticmethod
    def _resolve_cloudflare_client_ip(
        connection_ip: str | None, real_ip: str | None, cloudflare_connecting_ip: str | None
    ) -> str | None:
        # The address that reached Railway's edge
        edge_client_ip = real_ip or connection_ip
        if edge_client_ip is None or cloudflare_connecting_ip is None:
            return edge_client_ip
        # Cloudflare's header is only Cloudflare's when Cloudflare sent the request; one
        # that went around it keeps the address it really came from
        if not ClientIpUtils._is_cloudflare_ip(edge_client_ip):
            return edge_client_ip
        if ClientIpUtils._parse_ip(cloudflare_connecting_ip) is None:
            return edge_client_ip
        return cloudflare_connecting_ip

    @staticmethod
    def _is_cloudflare_ip(ip: str) -> bool:
        parsed_ip = ClientIpUtils._parse_ip(ip)
        if parsed_ip is None:
            return False
        return any(
            parsed_ip in cloudflare_ip_network for cloudflare_ip_network in CLOUDFLARE_IP_NETWORKS
        )

    @staticmethod
    def _parse_ip(ip: str) -> IPv4Address | IPv6Address | None:
        try:
            return ip_address(ip)
        except ValueError:
            return None


CLIENT_IP_RESOLVER_BY_SOURCE_TYPE: dict[
    ClientIpSourceType, Callable[[str | None, str | None, str | None], str | None]
] = {
    ClientIpSourceType.CONNECTION: ClientIpUtils._resolve_connection_client_ip,
    ClientIpSourceType.RAILWAY: ClientIpUtils._resolve_railway_client_ip,
    ClientIpSourceType.CLOUDFLARE: ClientIpUtils._resolve_cloudflare_client_ip,
}
