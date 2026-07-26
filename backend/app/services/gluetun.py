"""
Gluetun VPN control-server client and connection-safety checks.

When gluetun is configured, its control server gives an authoritative view of the
torrent client's real public IP and forwarded port (qBittorrent shares gluetun's
network namespace). Without gluetun, a heuristic falls back to qBittorrent's
interface binding.
"""

import logging
from typing import Dict, Any, Optional

from app.db import get_pool
from app.core.http_client import http_get, http_put, http_post

logger = logging.getLogger(__name__)


async def _load_gluetun_config() -> Optional[Dict[str, Any]]:
    """Load gluetun url + decrypted api key from the enabled download client."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT automation_settings FROM download_clients
            WHERE client_type = 'qbittorrent' AND is_enabled = TRUE
            LIMIT 1
            """)
    if not row:
        return None

    automation = row["automation_settings"]
    if isinstance(automation, str):
        import json

        try:
            automation = json.loads(automation)
        except Exception:
            automation = {}
    automation = automation or {}

    if not automation.get("gluetun_enabled"):
        return None

    url = (automation.get("gluetun_url") or "").rstrip("/")
    if not url:
        return None

    api_key = None
    encrypted = automation.get("gluetun_api_key")
    if encrypted:
        try:
            from app.api.v1.endpoints.setup import decrypt_value

            api_key = decrypt_value(encrypted)
        except Exception as e:
            logger.debug(f"Could not decrypt gluetun api key: {e}")

    # Fall back to the auto-generated control-server key from the secrets volume
    # so the user never has to copy it manually.
    if not api_key:
        try:
            import os

            key_path = os.path.join(os.getenv("KINORA_SECRETS_DIR", "."), "gluetun_api_key")
            if os.path.exists(key_path):
                with open(key_path) as f:
                    api_key = f.read().strip() or None
        except Exception:
            pass

    return {"url": url, "api_key": api_key}


def _auth_headers(config: Dict[str, Any]) -> Dict[str, str]:
    # Gluetun's control-server apikey auth reads the key from the X-API-Key header.
    if config.get("api_key"):
        return {"X-API-Key": config["api_key"]}
    return {}


class GluetunClient:
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url.rstrip("/")
        # Gluetun's control-server apikey auth reads the key from the X-API-Key header.
        self.headers = {"X-API-Key": api_key} if api_key else {}

    async def _get(self, path: str) -> Optional[Any]:
        try:
            resp = await http_get(f"{self.url}{path}", headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"Gluetun GET {path} failed: {e}")
        return None

    async def get_public_ip(self) -> Optional[Dict[str, Any]]:
        return await self._get("/v1/publicip/ip")

    async def get_vpn_status(self) -> Optional[str]:
        data = await self._get("/v1/vpn/status")
        return data.get("status") if isinstance(data, dict) else None

    async def get_version(self) -> Optional[str]:
        data = await self._get("/v1/version")
        if isinstance(data, dict):
            return data.get("version") or data.get("current")
        return None

    async def get_forwarded_port(self) -> Optional[int]:
        # The forwarded-port route differs across gluetun versions, so try both.
        for path in ("/v1/openvpn/portforwarded", "/v1/portforwarded"):
            data = await self._get(path)
            if isinstance(data, dict) and data.get("port"):
                return int(data["port"])
        return None

    async def set_vpn_status(self, status: str) -> bool:
        """status: 'running' | 'stopped'."""
        try:
            resp = await http_put(
                f"{self.url}/v1/vpn/status",
                json={"status": status},
                headers=self.headers,
            )
            return resp.status_code in (200, 202)
        except Exception as e:
            logger.warning(f"Gluetun set_vpn_status failed: {e}")
            return False


async def get_gluetun_client() -> Optional[GluetunClient]:
    config = await _load_gluetun_config()
    if not config:
        return None
    return GluetunClient(config["url"], config.get("api_key"))


async def get_kinora_public_ip() -> Optional[str]:
    """Fetch Kinora's own public IP from a public echo service."""
    try:
        resp = await http_get("https://api.ipify.org?format=json")
        if resp.status_code == 200:
            return resp.json().get("ip")
    except Exception as e:
        logger.debug(f"Public IP lookup failed: {e}")
    return None
