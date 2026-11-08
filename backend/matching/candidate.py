"""The candidate side of matching, built ONLY from user-confirmed resume facts."""
import hashlib
import re
from dataclasses import dataclass, field

from django.utils import timezone

from resumes.models import MasterResume, VerificationStatus

from .skills import expand_with_implied, find_skills

_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})\s*(?:-|\u2013|\u2014|to)\s*(?:[A-Za-z]{3,9}\.?\s+)?((?:19|20)\d{2}|present|current|now|ongoing)",
    re.IGNORECASE)
_LISTED = ("skill", "summary", "experience", "project", "certification")
_APPLIED = ("experience", "project")


@dataclass
class CandidateProfile:
    resume_id: str
    skills: set[str] = field(default_factory=set)  # listed or evidenced anywhere, plus implied skills
    applied_skills: set[str] = field(default_factory=set)  # evidenced in confirmed experience/projects
    implied_skills: set[str] = field(default_factory=set)
    total_years: float | None = None  # estimated from year ranges in confirmed experience facts
    has_experience_evidence: bool = False
    fact_count: int = 0
    fingerprint: str = ""


def estimate_years(texts: list[str]) -> float | None:
    """Union of the year ranges found in the texts (overlaps are not double counted)."""
    now_year = timezone.now().year
    ranges = []
    for text in texts:
        for start_text, end_text in _RANGE_RE.findall(text):
            start = int(start_text)
            end = now_year if not end_text.isdigit() else int(end_text)
            if 1970 <= start <= end <= now_year + 1:
                ranges.append((start, end))
    if not ranges:
        return None
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return float(sum(max(end - start, 0.5) for start, end in merged))


def build_candidate_profile(resume: MasterResume) -> CandidateProfile:
    facts = list(resume.facts.filter(verification_status=VerificationStatus.USER_CONFIRMED)
                 .order_by("position", "created_at"))
    listed: set[str] = set()
    applied: set[str] = set()
    for fact in facts:
        found = set(find_skills(fact.content))
        if fact.category in _LISTED:
            listed |= found
        if fact.category in _APPLIED:
            applied |= found
    all_skills = expand_with_implied(listed | applied)
    experience_texts = [f.content for f in facts if f.category == "experience"]
    digest = hashlib.sha256("\n".join(f"{f.id}:{f.category}:{f.content}" for f in facts).encode()).hexdigest()
    return CandidateProfile(
        resume_id=str(resume.id),
        skills=all_skills,
        applied_skills=expand_with_implied(applied),
        implied_skills=all_skills - listed - applied,
        total_years=estimate_years(experience_texts),
        has_experience_evidence=any(f.category in _APPLIED for f in facts),
        fact_count=len(facts),
        fingerprint=digest,
    )