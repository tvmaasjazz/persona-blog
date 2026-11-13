"""Exits non-zero when Cloudflare's published IP ranges differ from CLOUDFLARE_IP_NETWORKS.

Run from backend/, as the weekly workflow does:

    uv run python -m scripts.check_cloudflare_ips
"""

import sys
from ipaddress import IPv4Network, IPv6Network, ip_network

import httpx

from libs.users.constants import CLOUDFLARE_IP_NETWORKS

CLOUDFLARE_IPS_API_URL = "https://api.cloudflare.com/client/v4/ips"
REQUEST_TIMEOUT_SECONDS = 30


def _fetch_published_networks() -> set[IPv4Network | IPv6Network]:
    cloudflare_ips_response = httpx.get(CLOUDFLARE_IPS_API_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    cloudflare_ips_response.raise_for_status()
    cloudflare_ips = cloudflare_ips_response.json()["result"]
    published_cidrs = cloudflare_ips["ipv4_cidrs"] + cloudflare_ips["ipv6_cidrs"]
    return {ip_network(published_cidr) for published_cidr in published_cidrs}


def main() -> int:
    """Compares the ranges and prints any Cloudflare added or dropped."""
    published_networks = _fetch_published_networks()
    listed_networks = set(CLOUDFLARE_IP_NETWORKS)
    added_networks = sorted(map(str, published_networks - listed_networks))
    dropped_networks = sorted(map(str, listed_networks - published_networks))
    if not added_networks and not dropped_networks:
        print(f"CLOUDFLARE_IP_NETWORKS matches Cloudflare's {len(published_networks)} ranges.")
        return 0

    print("CLOUDFLARE_IP_NETWORKS in backend/libs/users/constants.py is out of date.")
    for added_network in added_networks:
        print(f"  add:    {added_network}")
    for dropped_network in dropped_networks:
        print(f"  remove: {dropped_network}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
