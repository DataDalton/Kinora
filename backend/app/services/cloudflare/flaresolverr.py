import httpx
from typing import Dict, Any
from app.core.config import settings
from app.services.cloudflare.base import BaseCloudflareBypass


class FlareSolverrBypass(BaseCloudflareBypass):
    """
    FlareSolverr implementation for bypassing Cloudflare protection
    """

    def __init__(self):
        self.api_url = settings.FLARESOLVERR_URL
        if not self.api_url:
            raise ValueError("FLARESOLVERR_URL not configured")

    async def get(self, url: str, max_timeout: int = 60000) -> Dict[str, Any]:
        """
        Make a GET request bypassing Cloudflare using FlareSolverr
        """
        async with httpx.AsyncClient(timeout=max_timeout / 1000) as client:
            response = await client.post(
                f"{self.api_url}/v1",
                json={
                    "cmd": "request.get",
                    "url": url,
                    "maxTimeout": max_timeout,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"FlareSolverr error: {data.get('message')}")

            return data

    async def post(
        self, url: str, post_data: str, max_timeout: int = 60000
    ) -> Dict[str, Any]:
        """
        Make a POST request bypassing Cloudflare using FlareSolverr
        """
        async with httpx.AsyncClient(timeout=max_timeout / 1000) as client:
            response = await client.post(
                f"{self.api_url}/v1",
                json={
                    "cmd": "request.post",
                    "url": url,
                    "postData": post_data,
                    "maxTimeout": max_timeout,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"FlareSolverr error: {data.get('message')}")

            return data

    async def test_connection(self) -> bool:
        """
        Test if FlareSolverr is reachable and working
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/")
                return response.status_code == 200
        except Exception:
            return False


flaresolverr = FlareSolverrBypass()
