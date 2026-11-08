"""Turns a source-specific ParsedListing into the internal Job shape.

Rule of thumb: when the source does not say something, the result is "unknown", never a guess.
"""
import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import EmploymentType, ExperienceLevel, RemoteEligibility, WorkArrangement
from .sources.base import ListingError, ParsedListing

# ---------- HTML -> plain text (we never store or render untrusted HTML) ----------

_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "tr", "section", "article",
               "h1", "h2", "h3", "h4", "h5", "h6"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")
            if tag == "li":
                self.parts.append("\u2022 ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS and tag != "li":  # a list item ends where the next one starts
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# ---------- titles, URLs, hashes ----------

_GENDER_RE = re.compile(r"\(\s*[mwfdx](?:\s*[/|]\s*[mwfdx])+\s*\)", re.IGNORECASE)


def normalize_title(title: str) -> str:
    cleaned = _GENDER_RE.sub(" ", title.lower())
    return re.sub(r"\s+", " ", cleaned).strip(" -\u2013|,")


def description_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


_TRACKING_KEYS = {"ref", "source", "gh_src", "fbclid", "gclid"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ListingError("Listing URL must be an http(s) URL.")
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), ""))


# ---------- countries and regions ----------

_COUNTRIES = {
    "ID": ["indonesia"], "SG": ["singapore"], "TH": ["thailand"], "MY": ["malaysia"], "VN": ["vietnam"],
    "PH": ["philippines"], "IN": ["india"], "AU": ["australia"], "NZ": ["new zealand"], "JP": ["japan"],
    "KR": ["south korea", "korea"], "HK": ["hong kong"], "TW": ["taiwan"], "CN": ["china"],
    "US": ["usa", "united states", "us", "u.s.", "united states of america"], "CA": ["canada"],
    "GB": ["uk", "united kingdom", "england", "great britain"], "IE": ["ireland"], "DE": ["germany", "deutschland"],
    "FR": ["france"], "ES": ["spain"], "PT": ["portugal"], "IT": ["italy"], "NL": ["netherlands"],
    "PL": ["poland"], "BR": ["brazil"], "MX": ["mexico"], "AR": ["argentina"], "ZA": ["south africa"],
    "AE": ["uae", "united arab emirates"], "TR": ["turkey"], "AT": ["austria"], "CH": ["switzerland"],
    "SE": ["sweden"], "DK": ["denmark"], "NO": ["norway"], "FI": ["finland"], "BE": ["belgium"],
}
_NAME_TO_CODE = {name: code for code, names in _COUNTRIES.items() for name in names}
_WORLDWIDE = {"anywhere", "worldwide", "global", "world"}
_APAC = {"apac", "asia", "asia pacific", "asia-pacific", "southeast asia", "sea", "indonesia"}
_REGIONS = {
    "europe": "EUROPE", "eu": "EU", "emea": "EMEA", "latam": "LATAM", "latin america": "LATAM",
    "north america": "NORTH_AMERICA", "americas": "AMERICAS", "africa": "AFRICA", "middle east": "MIDDLE_EAST",
}


def classify_geo(geo: str | None) -> tuple[str, list[str] | None]:
    """Who may apply to a remote job? Anything not clearly understood stays 'unknown'."""
    if not geo or not geo.strip():
        return RemoteEligibility.UNKNOWN, None
    countries, regions = [], []
    worldwide = apac = unknown = False
    for part in (p.strip().lower() for p in re.split(r"[,/;|&]|\band\b", geo)):
        if not part:
            continue
        if part in _WORLDWIDE:
            worldwide = True
        elif part in _APAC:
            apac = True
        elif part in _REGIONS:
            regions.append(_REGIONS[part])
        elif part in _NAME_TO_CODE:
            countries.append(_NAME_TO_CODE[part])
        else:
            unknown = True
    if unknown:
        return RemoteEligibility.UNKNOWN, None
    if worldwide and not (countries or regions or apac):
        return RemoteEligibility.WORLDWIDE, None
    if apac and not (countries or regions):
        return RemoteEligibility.APAC, None
    if countries and not (regions or apac):
        return RemoteEligibility.COUNTRY_SPECIFIC, sorted(set(countries))
    if countries or regions or apac:
        return RemoteEligibility.REGION_SPECIFIC, sorted(set(countries + regions + (["APAC"] if apac else [])))
    return RemoteEligibility.UNKNOWN, None


def country_from_location(location: str | None) -> str | None:
    """The job's own country, only when the location text names one explicitly."""
    if not location:
        return None
    for part in reversed([p.strip() for p in re.split(r"[,/|]", location) if p.strip()]):
        if part.lower() in _NAME_TO_CODE:
            return _NAME_TO_CODE[part.lower()]
        if len(part) == 2 and part.upper() in _COUNTRIES:
            return part.upper()
    return None


# ---------- work arrangement, type, level ----------

def detect_work_arrangement(remote: bool | None, location_text: str | None, title: str) -> str:
    text = f"{title} {location_text or ''}".lower()
    if re.search(r"\bhybrid\b", text):
        return WorkArrangement.HYBRID
    if remote is True or re.search(r"\bremote\b", text):
        return WorkArrangement.REMOTE
    if re.search(r"\bon[- ]?site\b", text):
        return WorkArrangement.ONSITE
    return WorkArrangement.UNKNOWN  # "not flagged remote" does not mean on-site


def map_employment_type(values: list[str]) -> str:
    for value in values:
        s = value.lower().replace("-", " ").replace("_", " ")
        if "intern" in s or "praktikum" in s:
            return EmploymentType.INTERNSHIP
        if "part" in s or "teilzeit" in s:
            return EmploymentType.PART_TIME
        if any(w in s for w in ("contract", "freelance", "temporary")):
            return EmploymentType.CONTRACT
        if "full" in s or "permanent" in s or "vollzeit" in s:
            return EmploymentType.FULL_TIME
    return EmploymentType.UNKNOWN


_LEVEL_PATTERNS = [
    (ExperienceLevel.GRADUATE, re.compile(r"\b(graduate|entry[- ]level|trainee)\b")),
    (ExperienceLevel.JUNIOR, re.compile(r"\b(junior|jr\.?)(?!\w)")),
    (ExperienceLevel.SENIOR, re.compile(r"\b(senior|sr\.?|lead|principal|staff)(?!\w)")),
    (ExperienceLevel.ASSOCIATE, re.compile(r"\bassociate\b")),
    (ExperienceLevel.MID, re.compile(r"\b(mid[- ]?level|midweight|mid|intermediate)\b")),
]


def detect_level(level_text: str | None, title: str) -> str:
    for text in (level_text, title):
        if not text or text.strip().lower() == "any":
            continue
        for level, pattern in _LEVEL_PATTERNS:
            if pattern.search(text.lower()):
                return level
    return ExperienceLevel.UNKNOWN


# ---------- the main entry point ----------

@dataclass
class NormalizedJob:
    job_fields: dict
    external_id: str | None
    original_url: str
    canonical_url: str
    metadata: dict


def normalize(parsed: ParsedListing) -> NormalizedJob:
    title = (parsed.title or "").strip()
    company = (parsed.company_name or "").strip()
    if not title or not company:
        raise ListingError("Listing has no title or company.")
    original_url = (parsed.url or "").strip()
    if len(original_url) > 1000:
        raise ListingError("Listing URL is too long.")
    canonical = canonical_url(original_url)  # also validates the scheme

    description = html_to_text(parsed.description)
    location = (parsed.location_text or "").strip()[:300] or None
    arrangement = detect_work_arrangement(parsed.remote, location, title)
    if arrangement == WorkArrangement.REMOTE:
        eligibility, eligible = classify_geo(parsed.geo_restriction)
    elif arrangement == WorkArrangement.UNKNOWN:
        eligibility, eligible = RemoteEligibility.UNKNOWN, None
    else:
        eligibility, eligible = RemoteEligibility.NOT_APPLICABLE, None

    currency = (parsed.salary_currency or "").upper()
    has_salary = parsed.salary_min is not None or parsed.salary_max is not None
    return NormalizedJob(
        job_fields={
            "title": title[:300],
            "normalized_title": normalize_title(title)[:300],
            "company_name": company[:200],
            "description": description,
            "location_text": location,
            "country_code": country_from_location(location),
            "work_arrangement": arrangement,
            "remote_eligibility": eligibility,
            "eligible_countries": eligible,
            "employment_type": map_employment_type(parsed.employment_types),
            "experience_level": detect_level(parsed.level_text, title),
            "salary_min": parsed.salary_min,
            "salary_max": parsed.salary_max,
            "salary_currency": currency if has_salary and len(currency) == 3 else None,
            "published_at": parsed.published_at,
            "description_hash": description_hash(description),
        },
        external_id=(parsed.external_id or None) and str(parsed.external_id)[:200],
        original_url=original_url,
        canonical_url=canonical,
        metadata=parsed.metadata,
    )