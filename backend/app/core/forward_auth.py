from typing import Optional, Dict
from ipaddress import ip_address, ip_network, IPv4Address, IPv6Address
from fastapi import Request

from app.core.config import settings


def is_ip_in_trusted_range(ip: str, trusted_ranges: list[str]) -> bool:
    """
    Check if an IP address is within any of the trusted IP ranges
    """
    try:
        client_ip = ip_address(ip)
        for range_str in trusted_ranges:
            if "/" in range_str:
                if client_ip in ip_network(range_str, strict=False):
                    return True
            else:
                if client_ip == ip_address(range_str):
                    return True
        return False
    except ValueError:
        return False


def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract the real client IP from request headers
    Checks X-Forwarded-For, X-Real-IP, and falls back to client host
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return None


def detect_authelia_headers(request: Request) -> Optional[Dict[str, str]]:
    """
    Detect and extract Authelia forward auth headers
    Returns dict with username and optional metadata, or None if not present
    """
    remote_user = request.headers.get("Remote-User")

    if not remote_user:
        return None

    return {
        "username": remote_user,
        "name": request.headers.get("Remote-Name", ""),
        "email": request.headers.get("Remote-Email", ""),
        "groups": request.headers.get("Remote-Groups", ""),
    }


def detect_authentik_headers(request: Request) -> Optional[Dict[str, str]]:
    """
    Detect and extract Authentik forward auth headers
    Returns dict with username and optional metadata, or None if not present
    """
    username = request.headers.get("X-authentik-username")

    if not username:
        return None

    return {
        "username": username,
        "name": request.headers.get("X-authentik-name", ""),
        "email": request.headers.get("X-authentik-email", ""),
        "groups": request.headers.get("X-authentik-groups", ""),
        "uid": request.headers.get("X-authentik-uid", ""),
    }


def detect_forward_auth(request: Request, trusted_ranges: Optional[list[str]] = None) -> Optional[Dict[str, any]]:
    """
    Detect forward authentication from Authelia or Authentik
    Returns dict with provider info and user data if valid, None otherwise

    Args:
        request: FastAPI request object
        trusted_ranges: List of trusted IP ranges (CIDR notation). If None, uses defaults from settings.

    Returns:
        Dict with keys: provider_type, provider_name, username, metadata
        None if no valid forward auth detected
    """
    if trusted_ranges is None:
        trusted_ranges = settings.FORWARD_AUTH_DEFAULT_TRUSTED_RANGES

    client_ip = get_client_ip(request)

    if not client_ip or not is_ip_in_trusted_range(client_ip, trusted_ranges):
        return None

    authelia_data = detect_authelia_headers(request)
    if authelia_data:
        return {
            "provider_type": "forward_auth",
            "provider_name": "authelia",
            "username": authelia_data["username"],
            "metadata": authelia_data,
        }

    authentik_data = detect_authentik_headers(request)
    if authentik_data:
        return {
            "provider_type": "forward_auth",
            "provider_name": "authentik",
            "username": authentik_data["username"],
            "metadata": authentik_data,
        }

    return None
