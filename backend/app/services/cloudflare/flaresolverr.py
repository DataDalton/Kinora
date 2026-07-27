import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.cache import getCacheClient
from app.services.cloudflare.base import BaseCloudflareBypass
from app.core.http_client import http_get, http_post

logger = logging.getLogger(__name__)

# Elects a single process to reap orphaned sessions when the stack starts. The TTL only
# needs to outlast the startup window, since the reap is a startup operation.
REAP_LOCK_KEY = "flaresolverr:reap"
REAP_LOCK_TTL = 300

# Fixed name for the session every Kinora process shares. The bypass object below is a
# module-level singleton, so each uvicorn worker and each Celery prefork child holds a
# separate copy carrying its own session id, and FlareSolverr backs every distinct
# session with its own browser. A constant name makes sessions.create idempotent across
# processes, which keeps the whole stack on one browser. FlareSolverr answers a repeat
# create with status ok and a "Session already exists" message.
SHARED_SESSION_ID = "kinora-shared"

# Marks sessions created by this app, so unrecognized ones can be identified and reaped.
SESSION_PREFIX = "kinora-"


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
        # Guards session creation against concurrent callers. Rebuilt whenever the running
        # loop changes, because Celery tasks run on a loop separate from the FastAPI one
        # and a lock holds a reference to the loop it was first awaited on.
        self._session_lock: Optional[asyncio.Lock] = None
        self._session_lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_session_lock(self) -> asyncio.Lock:
        """Return the session creation lock, bound to the running event loop."""
        loop = asyncio.get_running_loop()
        if self._session_lock is None or self._session_lock_loop is not loop:
            self._session_lock = asyncio.Lock()
            self._session_lock_loop = loop
        return self._session_lock

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
        Ensure the shared session exists, creating it on first use.
        Returns the session ID.

        Callers can arrive together, since a feed pull requests several 1337x
        categories at once through asyncio.gather. The lock lets the first caller
        create while the rest wait and reuse the result, instead of each issuing its
        own create.
        """
        if self.session_id:
            return self.session_id

        async with self._get_session_lock():
            # Set by whichever caller held the lock first.
            if self.session_id:
                return self.session_id

            self.session_id = await self.create_session(SHARED_SESSION_ID)
            return self.session_id

    async def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a FlareSolverr browser session, or adopt it when it already exists.
        Returns the session ID.
        """
        new_session_id = session_id or SHARED_SESSION_ID

        response = await http_post(
            f"{self.api_url}/v1",
            json={
                "cmd": "sessions.create",
                "session": new_session_id,
                "session_ttl_minutes": self.session_ttl_minutes,
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

        return await self._send(payload, use_session, max_timeout)

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

        return await self._send(payload, use_session, max_timeout)

    async def _send(self, payload: Dict[str, Any], use_session: bool, max_timeout: int) -> Dict[str, Any]:
        """
        Send a FlareSolverr command, attaching the shared session when requested.

        A session FlareSolverr no longer holds, after its container restarts or the
        idle TTL reclaims the browser, is recreated once and the command retried.
        Without that the shared name would keep pointing at a session that is gone.
        """
        for attempt in range(2):
            if use_session:
                try:
                    payload["session"] = await self._ensure_session()
                except Exception as e:
                    logger.warning(f"Failed to create session, proceeding without: {e}")
                    payload.pop("session", None)

            response = await http_post(
                f"{self.api_url}/v1",
                json=payload,
                timeout=max_timeout / 1000 + 10,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                self._capture_clearance(data)
                return data

            message = str(data.get("message") or "")
            retryable = use_session and attempt == 0 and "session" in message.lower()
            if not retryable:
                raise Exception(f"FlareSolverr error: {message}")

            logger.info(f"FlareSolverr no longer holds session {self.session_id}, recreating")
            self.session_id = None

        raise Exception("FlareSolverr error: session could not be reestablished")

    async def test_connection(self) -> bool:
        """
        Test if FlareSolverr is reachable and working.
        """
        try:
            response = await http_get(f"{self.api_url}/", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def reap_orphan_sessions(self) -> int:
        """
        Destroy every Kinora session other than the shared one and return how many
        were removed.

        FlareSolverr holds a session, and its browser, until something destroys it, so
        any session left behind by a process that has since exited keeps consuming
        memory for the life of the container. Running this at startup reclaims them.
        The shared session is left alone because other processes are using it.

        Every backend worker starts at once, so a cache flag elects one of them to do
        the work. The rest return immediately rather than racing to destroy the same
        sessions and logging the resulting misses.
        """
        client = await getCacheClient()
        if client is not None:
            try:
                elected = await client.set(REAP_LOCK_KEY, "1", ex=REAP_LOCK_TTL, nx=True)
                if not elected:
                    return 0
            except Exception as e:
                logger.warning(f"Could not claim the session reap lock, continuing: {e}")

        destroyed = 0
        for session in await self.list_sessions():
            if not session.startswith(SESSION_PREFIX) or session == SHARED_SESSION_ID:
                continue
            if await self.destroy_session(session):
                destroyed += 1

        if destroyed:
            logger.info(f"Destroyed {destroyed} orphaned FlareSolverr sessions")
        return destroyed


flaresolverr = FlareSolverrBypass()
