"""Requirement extraction from a job description. Deterministic and versioned (EXTRACTION_VERSION)."""
import re

from django.db import transaction

from jobs.models import Job

from .models import JobRequirements, JobSkill, RequirementType
from .skills import find_skills

EXTRACTION_VERSION = "v1"

_REQUIRED_HEADINGS = {
    "requirements", "required", "required skills", "qualifications", "minimum qualifications",
    "basic qualifications", "what you bring", "what were looking for", "what we are looking for",
    "must have", "must-have", "you have", "you will have", "your profile", "about you", "who you are",
    "skills", "key skills", "technical skills", "required qualifications", "what you need",
}
_PREFERRED_HEADINGS = {
    "nice to have", "nice-to-have", "preferred", "preferred qualifications", "preferred skills", "bonus",
    "bonus points", "good to have", "desirable", "pluses", "would be a plus", "extra credit",
}
_NEUTRAL_HEADINGS = {
    "responsibilities", "what youll do", "what you will do", "the role", "about the role", "about us",
    "about the job", "benefits", "we offer", "our stack", "tech stack", "your role", "the team",
    "about the team", "what we offer", "overview", "description",
}
_PREFERRED_CUE = re.compile(
    r"\b(nice to have|nice-to-have|preferred|bonus|a plus|is a plus|are a plus|ideally|desirable|"
    r"good to have|an advantage|an asset)\b|(?<!\d )(?<!\d\+ )\bplus\b", re.IGNORECASE)
_REQUIRED_CUE = re.compile(r"\b(required|must have|must-have|must|essential|mandatory)\b", re.IGNORECASE)
_RANK = {RequirementType.REQUIRED: 3, RequirementType.PREFERRED: 2, RequirementType.OPTIONAL: 1}

_YEARS_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|-\s*\d{1,2}|to\s*\d{1,2}|\u2013\s*\d{1,2})?\s*(?:years?|yrs?)\b['\u2019]?s?"
    r"(?:\s+of)?\s+((?:[A-Za-z#.+\-]+\s+){0,3}?)experience", re.IGNORECASE)
_GENERIC_WORDS = {
    "professional", "relevant", "work", "working", "industry", "software", "hands-on", "hands", "on",
    "commercial", "practical", "related", "development", "engineering", "proven", "solid", "real-world",
    "prior", "total", "overall", "of", "in", "backend", "back-end", "web", "programming",
}


def _heading_zone(line: str) -> tuple[str | None, str]:
    """If the line is a section heading, return (zone, any text after the colon)."""
    text = re.sub(r"^[\s#*\-\u2022]+", "", line).strip()
    before, colon, after = text.partition(":")
    key = re.sub(r"[^a-z\- ]", "", before.lower()).strip()
    key = re.sub(r"\s+", " ", key)
    if len(before) > 45 or not key:
        return None, ""
    # A heading either ends with ":" or is exactly a heading phrase on its own line.
    if not colon and key not in (_REQUIRED_HEADINGS | _PREFERRED_HEADINGS | _NEUTRAL_HEADINGS):
        return None, ""
    if key in _REQUIRED_HEADINGS:
        return "required", after
    if key in _PREFERRED_HEADINGS:
        return "preferred", after
    if key in _NEUTRAL_HEADINGS:
        return "neutral", after
    return None, ""


def _line_zone(line: str) -> str | None:
    if _PREFERRED_CUE.search(line):
        return "preferred"
    if _REQUIRED_CUE.search(line):
        return "required"
    return None


def extract_skills(title: str, description: str) -> dict[str, tuple[str, bool]]:
    """canonical skill -> (requirement type, is_uncertain). The strongest evidence wins."""
    result: dict[str, tuple[str, bool]] = {}

    def record(skill: str, rtype: str, uncertain: bool) -> None:
        current = result.get(skill)
        if current is None or _RANK[rtype] > _RANK[current[0]]:
            result[skill] = (rtype, uncertain)

    for skill in find_skills(title):
        record(skill, RequirementType.REQUIRED, False)  # a skill in the title is core to the role

    zone, zone_lines = None, 0
    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            if zone_lines:  # a blank line after the section's content ends the section
                zone, zone_lines = None, 0
            continue
        heading, rest = _heading_zone(line)
        if heading:
            zone, zone_lines, line = heading, 0, rest.strip()
            if not line:
                continue
        elif zone:
            zone_lines += 1
        effective = _line_zone(line) or zone
        for skill in find_skills(line):
            if effective == "required":
                record(skill, RequirementType.REQUIRED, False)
            elif effective == "preferred":
                record(skill, RequirementType.PREFERRED, False)
            else:  # mentioned, but nothing says whether it is needed
                record(skill, RequirementType.OPTIONAL, True)
    return result


def extract_years(text: str) -> tuple[int | None, bool]:
    """(minimum years of experience, uncertain). Per-skill requirements ('5 years of Python') are uncertain."""
    general, specific = [], []
    for match in _YEARS_RE.finditer(text):
        years = int(match.group(1))
        words = [w.lower() for w in match.group(2).split()]
        (general if all(w in _GENERIC_WORDS for w in words) else specific).append(years)
    if general:
        return min(general), len(set(general)) > 1
    if specific:
        return min(specific), True
    return None, False


@transaction.atomic
def extract_requirements(job: Job) -> JobRequirements:
    skills = extract_skills(job.title, job.description)
    min_years, years_uncertain = extract_years(job.description)
    requirements, _ = JobRequirements.objects.update_or_create(job=job, defaults={
        "extraction_version": EXTRACTION_VERSION, "description_hash": job.description_hash,
        "min_years_experience": min_years, "years_uncertain": years_uncertain,
    })
    job.skills.all().delete()
    JobSkill.objects.bulk_create([
        JobSkill(job=job, skill_name=name, normalized_name=name.lower(), requirement_type=rtype,
                 is_uncertain=uncertain)
        for name, (rtype, uncertain) in skills.items()
    ])
    return requirements


def needs_extraction(job: Job) -> bool:
    requirements = getattr(job, "requirements", None)
    return (requirements is None or requirements.extraction_version != EXTRACTION_VERSION
            or requirements.description_hash != job.description_hash)