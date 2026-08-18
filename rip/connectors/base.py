"""Connector base: polite HTTP (retries, backoff, rate-limit awareness).

Connectors only use official public APIs. They must respect rate limits and
never attempt to bypass authentication or anti-bot measures.
"""

import time
from abc import ABC, abstractmethod

import httpx

from ..normalize import NormalizedProfile


class RateLimitedError(RuntimeError):
    pass


class BaseConnector(ABC):
    source: str = "base"
    source_type: str = "generic"
    # polite minimum delay between requests, per connector instance
    min_request_interval: float = 0.5
    max_retries: int = 3

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=30.0, headers=self.default_headers())
        self._last_request_at = 0.0

    def default_headers(self) -> dict:
        return {"User-Agent": "resource-intelligence-platform/0.1 (research aggregator)"}

    def get_json(self, url: str, params: dict | None = None) -> dict | list:
        return self._request(url, params).json()

    def get_text(self, url: str, params: dict | None = None) -> str:
        return self._request(url, params).text

    def _request(self, url: str, params: dict | None = None) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            wait = self.min_request_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            resp = self._client.get(url, params=params)
            self._last_request_at = time.monotonic()
            if resp.status_code in (429, 403) and self._is_rate_limited(resp):
                retry_after = self._retry_after_seconds(resp)
                if retry_after is None or retry_after > 300 or attempt == self.max_retries:
                    raise RateLimitedError(
                        f"{self.source} rate limited (HTTP {resp.status_code}); "
                        f"retry after {retry_after or 'unknown'}s"
                    )
                time.sleep(retry_after)
                continue
            if resp.status_code >= 500 and attempt < self.max_retries:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"{self.source}: retries exhausted for {url}")

    def _is_rate_limited(self, resp: httpx.Response) -> bool:
        if resp.status_code == 429:
            return True
        return resp.headers.get("x-ratelimit-remaining") == "0"

    def _retry_after_seconds(self, resp: httpx.Response) -> float | None:
        if resp.headers.get("retry-after"):
            try:
                return float(resp.headers["retry-after"])
            except ValueError:
                return None
        reset = resp.headers.get("x-ratelimit-reset")
        if reset:
            try:
                return max(0.0, float(reset) - time.time())
            except ValueError:
                return None
        return None

    @abstractmethod
    def fetch(self, identifier: str) -> NormalizedProfile:
        """Fetch one person's public data and normalize it."""

    def renormalize(self, external_id: str, raw: dict) -> NormalizedProfile:
        """Re-run normalization from a stored raw payload — no network.

        Lets parser improvements be applied to the whole corpus as a cheap
        local rebuild instead of a full re-crawl.
        """
        raise NotImplementedError(f"{self.source} cannot renormalize from raw")
