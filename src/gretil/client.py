import asyncio
import logging
from pathlib import Path
from typing import Optional
import httpx

from .config import DEFAULT_CONCURRENCY, DEFAULT_HEADERS, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, REQUEST_DELAY

logger = logging.getLogger("gretil.client")


class GRETILClient:
    """HTTP client with caching, concurrency limiter, and exponential backoff retries."""

    def __init__(
        self,
        concurrency: int = DEFAULT_CONCURRENCY,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self.concurrency = concurrency
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(concurrency)
        self.limits = httpx.Limits(
            max_connections=concurrency * 2,
            max_keepalive_connections=concurrency,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(self.timeout),
            limits=self.limits,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch(
        self,
        url: str,
        cache_path: Optional[Path] = None,
        force: bool = False,
    ) -> str:
        """Fetch content of URL, reading from or writing to cache_path if given."""
        if cache_path and cache_path.exists() and not force:
            try:
                content = cache_path.read_text(encoding="utf-8")
                if content.strip():
                    return content
            except Exception as e:
                logger.warning(f"Error reading cache at {cache_path}: {e}")

        if not self._client:
            raise RuntimeError("GRETILClient must be used as an async context manager")

        async with self.semaphore:
            last_err = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = await self._client.get(url)
                    if resp.status_code == 200:
                        text = resp.text
                        if cache_path:
                            cache_path.parent.mkdir(parents=True, exist_ok=True)
                            cache_path.write_text(text, encoding="utf-8")
                        await asyncio.sleep(REQUEST_DELAY)
                        return text
                    elif resp.status_code == 404:
                        logger.warning(f"404 Not Found: {url}")
                        return ""
                    else:
                        logger.warning(
                            f"HTTP {resp.status_code} on {url} (attempt {attempt}/{self.max_retries})"
                        )
                except (httpx.RequestError, httpx.TimeoutException) as e:
                    last_err = e
                    logger.warning(
                        f"Request failed for {url} (attempt {attempt}/{self.max_retries}): {e}"
                    )

                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

            raise RuntimeError(
                f"Failed to fetch {url} after {self.max_retries} attempts: {last_err}"
            )
