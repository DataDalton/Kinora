import httpx
from typing import Optional

# Global shared HTTP client with connection pooling
_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """
    Get shared HTTP client with connection pooling and HTTP/3 support.
    Reuses connections across requests for better performance.
    Falls back to HTTP/2 if HTTP/3 is unavailable.
    """
    global _client

    if _client is None:
        # Try HTTP/3 first, fall back to HTTP/2
        try:
            _client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
                timeout=httpx.Timeout(30.0, connect=10.0),
                http2=True,
                http3=True,
                follow_redirects=True,
            )
        except TypeError:
            # http3 parameter not available, use HTTP/2
            _client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
                timeout=httpx.Timeout(30.0, connect=10.0),
                http2=True,
                follow_redirects=True,
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
