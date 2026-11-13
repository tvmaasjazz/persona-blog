import pytest

from libs.users.types import ClientIpSourceType
from libs.users.utils import ClientIpUtils
from libs.users.utils.client_ip_utils import CLIENT_IP_RESOLVER_BY_SOURCE_TYPE


@pytest.mark.parametrize("client_ip_source", list(ClientIpSourceType))
def test_client_ip_resolver_by_source_type_has_every_source(
    client_ip_source: ClientIpSourceType,
) -> None:
    assert client_ip_source in CLIENT_IP_RESOLVER_BY_SOURCE_TYPE


def test_resolve_client_ip_connection_ignores_proxy_headers() -> None:
    client_ip = ClientIpUtils.resolve_client_ip(
        client_ip_source=ClientIpSourceType.CONNECTION,
        connection_ip="10.0.0.5",
        real_ip="198.51.100.7",
        cloudflare_connecting_ip="203.0.113.9",
    )

    assert client_ip == "10.0.0.5"


@pytest.mark.parametrize(
    ("real_ip", "expected_client_ip"),
    [
        pytest.param("198.51.100.7", "198.51.100.7", id="real_ip_set"),
        pytest.param(None, "10.0.0.5", id="real_ip_missing"),
    ],
)
def test_resolve_client_ip_railway_returns_real_ip_else_connection(
    real_ip: str | None, expected_client_ip: str
) -> None:
    client_ip = ClientIpUtils.resolve_client_ip(
        client_ip_source=ClientIpSourceType.RAILWAY,
        connection_ip="10.0.0.5",
        real_ip=real_ip,
        cloudflare_connecting_ip="203.0.113.9",
    )

    assert client_ip == expected_client_ip


@pytest.mark.parametrize(
    ("real_ip", "cloudflare_connecting_ip"),
    [
        pytest.param("172.64.1.2", "203.0.113.9", id="ipv4_cloudflare_ipv4_client"),
        pytest.param("2606:4700::1", "2001:db8::9", id="ipv6_cloudflare_ipv6_client"),
    ],
)
def test_resolve_client_ip_cloudflare_from_cloudflare_returns_connecting_ip(
    real_ip: str, cloudflare_connecting_ip: str
) -> None:
    client_ip = ClientIpUtils.resolve_client_ip(
        client_ip_source=ClientIpSourceType.CLOUDFLARE,
        connection_ip="10.0.0.5",
        real_ip=real_ip,
        cloudflare_connecting_ip=cloudflare_connecting_ip,
    )

    assert client_ip == cloudflare_connecting_ip


@pytest.mark.parametrize(
    ("real_ip", "cloudflare_connecting_ip", "expected_client_ip"),
    [
        pytest.param("198.51.100.7", "203.0.113.9", "198.51.100.7", id="around_cloudflare"),
        pytest.param("172.64.1.2", None, "172.64.1.2", id="connecting_ip_missing"),
        pytest.param("172.64.1.2", "not-an-ip", "172.64.1.2", id="connecting_ip_invalid"),
        pytest.param("not-an-ip", "203.0.113.9", "not-an-ip", id="real_ip_invalid"),
    ],
)
def test_resolve_client_ip_cloudflare_untrusted_connecting_ip_returns_real_ip(
    real_ip: str, cloudflare_connecting_ip: str | None, expected_client_ip: str
) -> None:
    client_ip = ClientIpUtils.resolve_client_ip(
        client_ip_source=ClientIpSourceType.CLOUDFLARE,
        connection_ip="10.0.0.5",
        real_ip=real_ip,
        cloudflare_connecting_ip=cloudflare_connecting_ip,
    )

    assert client_ip == expected_client_ip


def test_resolve_client_ip_cloudflare_real_ip_missing_returns_connection_ip() -> None:
    client_ip = ClientIpUtils.resolve_client_ip(
        client_ip_source=ClientIpSourceType.CLOUDFLARE,
        connection_ip="10.0.0.5",
        real_ip=None,
        cloudflare_connecting_ip="203.0.113.9",
    )

    assert client_ip == "10.0.0.5"


def test_resolve_client_ip_cloudflare_no_address_returns_none() -> None:
    client_ip = ClientIpUtils.resolve_client_ip(
        client_ip_source=ClientIpSourceType.CLOUDFLARE,
        connection_ip=None,
        real_ip=None,
        cloudflare_connecting_ip=None,
    )

    assert client_ip is None
