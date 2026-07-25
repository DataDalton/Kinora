import uuid
import logging
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.services.cloudflare.base import BaseCloudflareBypass
from app.core.http_client import http_get, http_post

logger = logging.getLogger(__name__)


class FlareSolverrBypass(BaseCloudflareBypass):
    """
    FlareSolverr implementation for bypassing Cloudflare protection.
    Uses persistent sessions and disables media loading for faster requests.
    """

    def __init__(self):
        self.api_url = settings.FLARESOLVERR_URL
        if not self.api_url:
            raise ValueError("FLARESOLVERR_URL not configured")
        self.session_id: Optional[str] = None
        self.session_ttl_minutes: int = 30
        # Cloudflare clearance from the last successful solve. Reused by indexers to
        # fetch follow-up pages with a plain impersonating HTTP client instead of the
        # browser (verified to pass 1337x when backend and FlareSolverr share an egress IP).
        self.clearance_cookies: Dict[str, str] = {}
        self.user_agent: Optional[str] = None

    def _capture_clearance(self, data: Dict[str, Any]) -> None:
        """Store the cf_clearance cookies and user-agent from a FlareSolverr solution."""
        solution = data.get("solution") or {}
        cookies = solution.get("cookies") or []
        parsed = {c["name"]: c["value"] for c in cookies if c.get("name") and c.get("value")}
        if parsed:
            self.clearance_cookies = parsed
        user_agent = solution.get("userAgent")
        if user_agent:
            self.user_agent = user_agent

    async def _ensure_session(self) -> str:
        """
        Ensure a session exists, creating one if needed.
        Returns the session ID.
        """
        if self.session_id:
            sessions = await self.list_sessions()
            if self.session_id in sessions:
                return self.session_id
            logger.info(f"Session {self.session_id} expired, creating new one")

        self.session_id = await self.create_session()
        return self.session_id

    async def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new FlareSolverr browser session.
        Returns the session ID.
        """
        new_session_id = session_id or f"kinora-{uuid.uuid4().hex[:8]}"

        response = await http_post(
            f"{self.api_url}/v1",
            json={
                "cmd": "sessions.create",
                "session": new_session_id,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            raise Exception(f"FlareSolverr session create error: {data.get('message')}")

        logger.info(f"Created FlareSolverr session: {new_session_id}")
        return new_session_id

    async def destroy_session(self, session_id: Optional[str] = None) -> bool:
        """
        Destroy a FlareSolverr browser session.
        """
        target_session = session_id or self.session_id
        if not target_session:
            return False

        try:
            response = await http_post(
                f"{self.api_url}/v1",
                json={
                    "cmd": "sessions.destroy",
                    "session": target_session,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                logger.info(f"Destroyed FlareSolverr session: {target_session}")
                if target_session == self.session_id:
                    self.session_id = None
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to destroy session {target_session}: {e}")
            return False

    async def list_sessions(self) -> List[str]:
        """
        List all active FlareSolverr sessions.
        """
        try:
            response = await http_post(
                f"{self.api_url}/v1",
                json={"cmd": "sessions.list"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return data.get("sessions", [])
            return []
        except Exception as e:
            logger.warning(f"Failed to list sessions: {e}")
            return []

    async def get(
        self,
        url: str,
        max_timeout: int = 60000,
        use_session: bool = True,
        disable_media: bool = True,
    ) -> Dict[str, Any]:
        """
        Make a GET request bypassing Cloudflare using FlareSolverr.

        Args:
            url: Target URL
            max_timeout: Max timeout in milliseconds
            use_session: Whether to use persistent session (reuses browser instance)
            disable_media: Skip loading images, CSS, fonts for faster requests
        """
        payload: Dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout,
        }

        if disable_media:
            payload["disableMedia"] = True

        if use_session:
            try:
                payload["session"] = await self._ensure_session()
                payload["session_ttl_minutes"] = self.session_ttl_minutes
            except Exception as e:
                logger.warning(f"Failed to create session, proceeding without: {e}")

        response = await http_post(
            f"{self.api_url}/v1",
            json=payload,
            timeout=max_timeout / 1000 + 10,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            raise Exception(f"FlareSolverr error: {data.get('message')}")

        self._capture_clearance(data)
        return data

    async def post(
        self,
        url: str,
        post_data: str,
        max_timeout: int = 60000,
        use_session: bool = True,
        disable_media: bool = True,
    ) -> Dict[str, Any]:
        """
        Make a POST request bypassing Cloudflare using FlareSolverr.

        Args:
            url: Target URL
            post_data: Form-encoded POST data
            max_timeout: Max timeout in milliseconds
            use_session: Whether to use persistent session (reuses browser instance)
            disable_media: Skip loading images, CSS, fonts for faster requests
        """
        payload: Dict[str, Any] = {
            "cmd": "request.post",
            "url": url,
            "postData": post_data,
            "maxTimeout": max_timeout,
        }

        if disable_media:
            payload["disableMedia"] = True

        if use_session:
            try:
                payload["session"] = await self._ensure_session()
                payload["session_ttl_minutes"] = self.session_ttl_minutes
            except Exception as e:
                logger.warning(f"Failed to create session, proceeding without: {e}")

        response = await http_post(
            f"{self.api_url}/v1",
            json=payload,
            timeout=max_timeout / 1000 + 10,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            raise Exception(f"FlareSolverr error: {data.get('message')}")

        self._capture_clearance(data)
        return data

    async def test_connection(self) -> bool:
        """
        Test if FlareSolverr is reachable and working.
        """
        try:
            response = await http_get(f"{self.api_url}/", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def cleanup(self) -> None:
        """
        Cleanup resources by destroying the current session.
        Call this during application shutdown.
        """
        if self.session_id:
            await self.destroy_session()


flaresolverr = FlareSolverrBypass()
