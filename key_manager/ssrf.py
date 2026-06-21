"""SSRF protection for custom_base_url parameter."""

import socket
import urllib.parse
from ipaddress import ip_address, ip_network

from key_manager.errors import ErrorCode, ValidationError

BLOCKED_NETWORKS = [
    # IPv4 private ranges
    ip_network("127.0.0.0/8"),
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("169.254.0.0/16"),
    # IPv6 private ranges
    ip_network("::1/128"),      # Loopback
    ip_network("fc00::/7"),     # Unique local
    ip_network("fe80::/10"),    # Link-local
    ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def validate_custom_base_url(url: str, allowed_domains: set[str]) -> str:
    """Validate custom_base_url against allowed provider domains.

    Raises ValidationError if URL is not safe.
    """
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValidationError(
            code=ErrorCode.VALIDATION_INVALID_FORMAT,
            message="Only http/https URLs allowed",
        )

    hostname = parsed.hostname or ""

    if hostname in BLOCKED_HOSTS:
        raise ValidationError(
            code=ErrorCode.VALIDATION_INVALID_FORMAT,
            message="Localhost not allowed",
        )

    # Check allowed domains first (skip DNS resolution for known domains)
    if allowed_domains and hostname in allowed_domains:
        return url

    # Check if hostname is an IP address
    try:
        ip = ip_address(hostname)
        for net in BLOCKED_NETWORKS:
            if ip in net:
                raise ValidationError(
                    code=ErrorCode.VALIDATION_INVALID_FORMAT,
                    message="Private IP addresses not allowed",
                )
    except ValueError:
        # Not an IP, resolve domain to check for DNS rebinding
        try:
            resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _family, _, _, _, sockaddr in resolved_ips:
                ip = ip_address(sockaddr[0])
                for net in BLOCKED_NETWORKS:
                    if ip in net:
                        raise ValidationError(
                            code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Domain '{hostname}' resolves to private IP {ip}",
                        )
        except socket.gaierror:
            raise ValidationError(
                code=ErrorCode.VALIDATION_INVALID_FORMAT,
                message=f"Cannot resolve domain '{hostname}'",
            )

    if allowed_domains and hostname not in allowed_domains:
        raise ValidationError(
            code=ErrorCode.VALIDATION_INVALID_FORMAT,
            message=f"Domain '{hostname}' not in allowed provider list",
        )

    return url


def get_allowed_domains(providers: dict) -> set[str]:
    """Extract allowed domains from provider base URLs."""
    domains = set()
    for provider in providers.values():
        parsed = urllib.parse.urlparse(provider.base_url)
        if parsed.hostname:
            domains.add(parsed.hostname)
    return domains
