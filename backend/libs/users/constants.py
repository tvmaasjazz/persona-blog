from ipaddress import ip_network

USER_ACTIVITY_KEY_PREFIX = "user-activity:"
# Only the throttle key's presence matters; its value is never read
USER_ACTIVITY_KEY_VALUE = "1"
# Followed by the UTC date, so each day has its own salt
ANONYMOUS_USER_KEY_SALT_KEY_PREFIX = "anonymous-user-key-salt:"

# Set by Railway's edge to the address that connected to it, overwriting any sent in
REAL_IP_HEADER_NAME = "X-Real-IP"
# Set by Cloudflare to the client's address; anyone can send it, so it's trusted only
# from a request that came from one of Cloudflare's addresses
CLOUDFLARE_CONNECTING_IP_HEADER_NAME = "CF-Connecting-IP"
# Cloudflare's published ranges (https://www.cloudflare.com/ips/). The weekly
# cloudflare-ips workflow fails when they change; update this list to match
CLOUDFLARE_IP_NETWORKS = tuple(
    ip_network(cloudflare_ip_network)
    for cloudflare_ip_network in (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)
