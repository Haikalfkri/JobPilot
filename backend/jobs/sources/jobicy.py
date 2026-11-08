"""Jobicy remote jobs (public JSON API, no key). Respect their fair use: few calls per day, credit the source."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from django.conf import settings

from .base import BaseAdapter, ListingError, ParsedListing, SourceError


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _decimal(value) -> Decimal | None:
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None
    return number if number > 0 else None


class JobicyAdapter(BaseAdapter):
    source_key = "jobicy"
    display_name = "Jobicy"
    source_type = "api"
    base_url = "https://jobicy.com"
    api_url = "https://jobicy.com/api/v2/remote-jobs"
    allowed_hosts = frozenset({"jobicy.com", "www.jobicy.com"})

    def search(self, criteria: dict):
        keywords = [k.strip() for k in criteria.get("keywords", []) if 3 <= len(k.strip()) <= 50]
        keywords = keywords[: settings.DISCOVERY_MAX_KEYWORDS]
        queries = [{"count": 50, "tag": k} for k in keywords] or [{"count": 50}]
        seen: set[str] = set()
        with self._http() as client:
            for index, params in enumerate(queries):
                if index:
                    self._pause()
                data = self._get_json(client, self.api_url, params)
                jobs = data.get("jobs") or []
                if not isinstance(jobs, list):
                    raise SourceError("BAD_RESPONSE", f"{self.display_name} returned an unexpected response.")
                for raw in jobs:
                    key = str(raw.get("id")) if isinstance(raw, dict) else None
                    if key is not None:
                        if key in seen:
                            continue
                        seen.add(key)
                    yield raw

    def parse(self, raw: dict) -> ParsedListing:
        if not isinstance(raw, dict):
            raise ListingError("Listing is not an object.")
        geo = raw.get("jobGeo")
        levels = _as_list(raw.get("jobLevel"))
        return ParsedListing(
            external_id=str(raw["id"]) if raw.get("id") is not None else None,
            url=str(raw.get("url") or ""),
            title=str(raw.get("jobTitle") or ""),
            company_name=str(raw.get("companyName") or ""),
            description=str(raw.get("jobDescription") or raw.get("jobExcerpt") or ""),
            location_text=None,  # jobGeo is a restriction on applicants, not the job's location
            remote=True,  # every Jobicy listing is a remote job
            geo_restriction=", ".join(_as_list(geo)) or None,
            employment_types=_as_list(raw.get("jobType")),
            level_text=levels[0] if levels else None,
            published_at=self._parse_date(raw.get("pubDate")),
            salary_min=_decimal(raw.get("annualSalaryMin")),
            salary_max=_decimal(raw.get("annualSalaryMax")),
            salary_currency=(str(raw["salaryCurrency"]).upper() if raw.get("salaryCurrency") else None),
            metadata={"industry": _as_list(raw.get("jobIndustry")), "job_geo": geo},
        )

    @staticmethod
    def _parse_date(value) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        # Jobicy sends no timezone. Assumption: UTC.
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)