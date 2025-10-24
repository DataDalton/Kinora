from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseCloudflareBypass(ABC):
    """
    Base class for Cloudflare bypass implementations
    """

    @abstractmethod
    async def get(self, url: str, max_timeout: int = 60000) -> Dict[str, Any]:
        """
        Make a GET request bypassing Cloudflare protection
        Returns dict with 'solution' containing response text and cookies
        """
        pass

    @abstractmethod
    async def post(
        self, url: str, post_data: str, max_timeout: int = 60000
    ) -> Dict[str, Any]:
        """
        Make a POST request bypassing Cloudflare protection
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the bypass service is reachable and working
        """
        pass
