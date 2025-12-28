from curl_cffi.requests import AsyncSession, Response
from typing import Optional, Any, Callable, TypeVar
from functools import wraps
import asyncio

# Type variable for generic return types
T = TypeVar('T')

# Global shared HTTP client
_client: Optional[AsyncSession] = None

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_BACKOFF = 0.5
RETRY_BACKOFF_MULTIPLIER = 2.0
RETRY_MAX_BACKOFF = 8.0
RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def retryWithBackoff(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that adds retry logic with exponential backoff.
    Retries on connection errors, timeouts, and specific HTTP status codes.
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        lastException = None
        backoff = RETRY_INITIAL_BACKOFF

        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                response = await func(*args, **kwargs)

                # Check if response status code should trigger retry
                if hasattr(response, 'status_code') and response.status_code in RETRY_STATUS_CODES:
                    if attempt < RETRY_MAX_ATTEMPTS - 1:
                        print(f"HTTP {response.status_code} - retrying in {backoff}s (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * RETRY_BACKOFF_MULTIPLIER, RETRY_MAX_BACKOFF)
                        continue

                return response

            except (ConnectionError, TimeoutError, OSError) as e:
                lastException = e
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    print(f"Connection error: {e} - retrying in {backoff}s (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * RETRY_BACKOFF_MULTIPLIER, RETRY_MAX_BACKOFF)
                else:
                    raise

            except Exception as e:
                # Check for curl_cffi specific timeout/connection errors
                errorStr = str(e).lower()
                if 'timeout' in errorStr or 'connection' in errorStr or 'refused' in errorStr:
                    lastException = e
                    if attempt < RETRY_MAX_ATTEMPTS - 1:
                        print(f"Request error: {e} - retrying in {backoff}s (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * RETRY_BACKOFF_MULTIPLIER, RETRY_MAX_BACKOFF)
                    else:
                        raise
                else:
                    raise

        if lastException:
            raise lastException

    return wrapper

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


@retryWithBackoff
async def http_get(url: str, **kwargs: Any) -> Response:
    """HTTP GET with HTTP/3 priority and automatic retry."""
    client = await get_http_client()
    kwargs.setdefault("http_version", HTTP_VERSION)
    return await client.get(url, **kwargs)


@retryWithBackoff
async def http_post(url: str, **kwargs: Any) -> Response:
    """HTTP POST with HTTP/3 priority and automatic retry."""
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
