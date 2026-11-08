"""Arbeitnow job board (public JSON API, no key). Mostly Europe-based jobs, some remote."""
from datetime import datetime, timezone

from django.conf import settings

from .base import BaseAdapter, ListingError, ParsedListing, SourceError


def _matches(raw, keywords: list[str]) -> bool:
    """Arbeitnow has no keyword search, so filter client-side on title, tags and description."""
    if not keywords:
        return True
    if not isinstance(raw, dict):
        return False
    haystack = " ".join(
        [str(raw.get("title", "")), " ".join(map(str, raw.get("tags") or [])), str(raw.get("description", ""))]
    ).lower()
    return any(keyword in haystack for keyword in keywords)


class ArbeitnowAdapter(BaseAdapter):
    source_key = "arbeitnow"
    display_name = "Arbeitnow"
    source_type = "api"
    base_url = "https://www.arbeitnow.com"
    api_url = "https://www.arbeitnow.com/api/job-board-api"
    allowed_hosts = frozenset({"www.arbeitnow.com", "arbeitnow.com"})

    def search(self, criteria: dict):
        keywords = [k.strip().lower() for k in criteria.get("keywords", []) if k.strip()]
        with self._http() as client:
            for page in range(1, settings.DISCOVERY_ARBEITNOW_MAX_PAGES + 1):
                if page > 1:
                    self._pause()
                data = self._get_json(client, self.api_url, {"page": page})
                items = data.get("data")
                if not isinstance(items, list):
                    raise SourceError("BAD_RESPONSE", f"{self.display_name} returned an unexpected response.")
                if not items:
                    return
                for raw in items:
                    if _matches(raw, keywords):
                        yield raw
                if not (data.get("links") or {}).get("next"):
                    return

    def parse(self, raw: dict) -> ParsedListing:
        if not isinstance(raw, dict):
            raise ListingError("Listing is not an object.")
        job_types = raw.get("job_types") or []
        return ParsedListing(
            external_id=str(raw["slug"]) if raw.get("slug") else None,
            url=str(raw.get("url") or ""),
            title=str(raw.get("title") or ""),
            company_name=str(raw.get("company_name") or ""),
            description=str(raw.get("description") or ""),
            location_text=str(raw["location"]) if raw.get("location") else None,
            remote=bool(raw["remote"]) if "remote" in raw else None,
            geo_restriction=None,  # Arbeitnow does not say who may apply to a remote job
            employment_types=[str(t) for t in job_types] if isinstance(job_types, list) else [],
            level_text=None,
            published_at=self._from_epoch(raw.get("created_at")),
            metadata={"tags": [str(t) for t in (raw.get("tags") or [])][:20]},
        )

    @staticmethod
    def _from_epoch(value) -> datetime | None:
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return None