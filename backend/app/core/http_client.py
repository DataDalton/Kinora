import httpx
from typing import Optional

# Global shared HTTP client with connection pooling
_client: Optional[httpx.AsyncClient] = None

# Default headers for all requests
DEFAULT_HEADERS = {
    "User-Agent": "Nexarr/1.0 (Media Management Platform)",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
}


async def get_http_client() -> httpx.AsyncClient:
    """
    Get shared HTTP client with connection pooling.
    HTTP/3 is automatically negotiated when httpx[http3] is installed.
    HTTP/2 is enabled as fallback. Connection reuse across requests.
    """
    global _client

    if _client is None:
        _client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=30,
                keepalive_expiry=60.0,
            ),
            timeout=httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=30.0,
                pool=10.0,
            ),
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )

    return _client


async def close_http_client():
    """
    Close the shared HTTP client. Call on application shutdown.
    """
    global _client

    if _client is not None:
        await _client.aclose()
        _client = None
