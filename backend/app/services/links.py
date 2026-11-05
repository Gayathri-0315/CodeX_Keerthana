"""Check that an apply / registration link actually opens, before students tap it.

Safety: only http(s); the host must resolve to public addresses (never localhost, private, link-local or
cloud-metadata IPs), so this can't be used to probe the server's own network. Redirects are followed by
hand and each hop is checked the same way. Short timeout; we only read the status, never the page.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

TIMEOUT = 5.0
MAX_REDIRECTS = 4
UNREACHABLE = "We couldn't open this link. Check the address, or make sure the page is public."
NOT_FOUND = "This link opens a 'page not found'. Check the address."


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(infos)


def check(url: str) -> str | None:
    """None if the link opens; otherwise a short reason for the organizer."""
    current = url.strip()
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": "ShowUp link check"}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlparse(current)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                return "Use a full web address starting with https://"
            if not _public_host(parts.hostname):
                return UNREACHABLE
            try:
                r = client.get(current)
            except httpx.HTTPError:
                return UNREACHABLE
            if r.is_redirect and r.headers.get("location"):
                current = urljoin(current, r.headers["location"])
                continue
            if r.status_code in (404, 410):
                return NOT_FOUND
            if r.status_code >= 500:
                return UNREACHABLE
            return None  # 2xx, or 401/403/405/429: the site is there, it just doesn't like robots
    return UNREACHABLE
