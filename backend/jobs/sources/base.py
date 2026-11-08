"""Shared pieces for job source adapters.

An adapter only knows how to fetch listings from ONE source and turn each raw listing into a
ParsedListing. Everything source-independent lives in jobs/normalization.py.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Protocol

import httpx
from django.conf import settings

USER_AGENT = "JobPilot/0.1 (personal local job-search assistant)"


class SourceError(Exception):
    """The whole source failed (network, rate limit, bad response). Safe to show to the user."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ListingError(ValueError):
    """One listing is unusable. It is skipped; the rest of the source continues."""


@dataclass
class ParsedListing:
    external_id: str | None
    url: str
    title: str
    company_name: str
    description: str = ""  # may contain HTML; the normalizer converts it to plain text
    location_text: str | None = None
    remote: bool | None = None  # None means the source does not say
    geo_restriction: str | None = None  # where remote applicants must live, as the source words it
    employment_types: list[str] = field(default_factory=list)
    level_text: str | None = None
    published_at: datetime | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    metadata: dict = field(default_factory=dict)  # small, source-specific extras


class JobSourceAdapter(Protocol):
    source_key: str
    display_name: str
    source_type: str
    base_url: str
    allowed_hosts: frozenset[str]

    def search(self, criteria: dict) -> Iterable[dict]: ...

    def parse(self, raw_listing: dict) -> ParsedListing: ...


class BaseAdapter:
    """HTTP helpers shared by API-based adapters. The client is injectable so tests need no network."""

    source_key = ""
    display_name = ""

    def __init__(self, client: httpx.Client | None = None, sleep=time.sleep):
        self._client = client
        self._sleep = sleep

    @contextmanager
    def _http(self):
        if self._client is not None:
            yield self._client
            return
        with httpx.Client(
            timeout=settings.DISCOVERY_REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            yield client

    def _pause(self) -> None:
        """Be polite between requests to the same source."""
        if settings.DISCOVERY_REQUEST_DELAY_SECONDS > 0:
            self._sleep(settings.DISCOVERY_REQUEST_DELAY_SECONDS)

    def _get_json(self, client: httpx.Client, url: str, params: dict | None = None) -> dict:
        try:
            response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceError("NETWORK_ERROR", f"Could not reach {self.display_name}.") from exc
        if response.status_code == 429:
            # Never retry a rate limit automatically.
            raise SourceError("RATE_LIMITED", f"{self.display_name} is rate limiting requests. Try again later.")
        if response.status_code >= 400:
            raise SourceError(f"HTTP_{response.status_code}", f"{self.display_name} returned an error.")
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError("BAD_RESPONSE", f"{self.display_name} returned an unreadable response.") from exc
        if not isinstance(data, dict):
            raise SourceError("BAD_RESPONSE", f"{self.display_name} returned an unexpected response.")
        return data