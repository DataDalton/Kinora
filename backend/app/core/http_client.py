from curl_cffi.requests import AsyncSession, Response
from typing import Optional, Any

# Global shared HTTP client
_client: Optional[AsyncSession] = None

# Default headers for API requests
DEFAULT_HEADERS = {
    "User-Agent": "Nexarr/1.0",
    "Accept": "application/json",
}

# HTTP/3 with automatic fallback to HTTP/2 and HTTP/1.1
HTTP_VERSION = "v3"


async def get_http_client() -> AsyncSession:
    """
    Get shared async HTTP client with connection pooling.
    Uses HTTP/3 by default with automatic fallback to HTTP/2.
    """
    global _client

    if _client is None:
        _client = AsyncSession(
            headers=DEFAULT_HEADERS,
            timeout=30.0,
            allow_redirects=True,
            max_redirects=10,
            max_clients=100,
        )

    return _client


async def close_http_client():
    """Close the shared HTTP client. Call on application shutdown."""
    global _client

    if _client is not None:
        await _client.close()
        _client = None


async def http_get(url: str, **kwargs: Any) -> Response:
    """HTTP GET with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.get(url, **kwargs)


async def http_post(url: str, **kwargs: Any) -> Response:
    """HTTP POST with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.post(url, **kwargs)


async def http_put(url: str, **kwargs: Any) -> Response:
    """HTTP PUT with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.put(url, **kwargs)


async def http_patch(url: str, **kwargs: Any) -> Response:
    """HTTP PATCH with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.patch(url, **kwargs)


async def http_delete(url: str, **kwargs: Any) -> Response:
    """HTTP DELETE with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.delete(url, **kwargs)


async def http_head(url: str, **kwargs: Any) -> Response:
    """HTTP HEAD with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.head(url, **kwargs)


async def http_request(method: str, url: str, **kwargs: Any) -> Response:
    """Generic HTTP request with HTTP/3 priority."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.request(method, url, **kwargs)
