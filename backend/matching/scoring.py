"""Pure, deterministic scoring. No database access: every input is passed in, so results are repeatable.

Final score = weighted average of the components that could be assessed. A component that cannot be
assessed (for example the job states no skills) is left out and reported as not assessed, never guessed.
"""
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .candidate import CandidateProfile

SCORING_VERSION = "v1"
COMPONENTS = ["skills", "experience", "title", "seniority", "location"]
SKILL_WEIGHTS = {"required": 3, "preferred": 1, "optional": 1}
LEVEL_RANK = {"graduate": 0, "junior": 1, "associate": 2, "mid": 3, "senior": 4}
ALL_ARRANGEMENTS = ["remote", "hybrid", "onsite"]

REGIONS = {
    "APAC": {"ID", "SG", "TH", "MY", "VN", "PH", "IN", "AU", "NZ", "JP", "KR", "HK", "TW", "CN"},
    "EUROPE": {"GB", "IE", "DE", "FR", "ES", "PT", "IT", "NL", "PL", "AT", "CH", "SE", "DK", "NO", "FI", "BE", "TR"},
    "EU": {"IE", "DE", "FR", "ES", "PT", "IT", "NL", "PL", "AT", "SE", "DK", "FI", "BE"},
    "EMEA": {"GB", "IE", "DE", "FR", "ES", "PT", "IT", "NL", "PL", "AT", "CH", "SE", "DK", "NO", "FI", "BE",
             "TR", "ZA", "AE"},
    "LATAM": {"BR", "MX", "AR"},
    "NORTH_AMERICA": {"US", "CA", "MX"},
    "AMERICAS": {"US", "CA", "MX", "BR", "AR"},
    "AFRICA": {"ZA"},
    "MIDDLE_EAST": {"AE", "TR"},
}
KNOWN_COUNTRIES = set().union(*REGIONS.values())


# ---------- inputs ----------

@dataclass
class SkillReq:
    name: str
    requirement_type: str  # required | preferred | optional
    is_uncertain: bool


@dataclass
class JobView:
    title: str
    work_arrangement: str
    remote_eligibility: str
    eligible_countries: list[str] | None
    country_code: str | None
    location_text: str | None
    experience_level: str
    skills: list[SkillReq]
    min_years: int | None
    years_uncertain: bool


@dataclass
class Preferences:
    job_titles: list[str]
    target_locations: list[dict]
    work_arrangements: list[str]
    experience_levels: list[str]
    candidate_countries: list[str]
    weights: dict[str, float]


@dataclass
class Component:
    score: float | None
    detail: str


@dataclass
class LocationResult:
    score: float | None
    status: str
    reasons: list[str]


@dataclass
class MatchResult:
    overall: float
    coverage: float
    components: dict[str, Component]
    eligibility_status: str
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    uncertain_requirements: list[str] = field(default_factory=list)
    location_reasons: list[str] = field(default_factory=list)
    explanation: str = ""


# ---------- skills ----------

def _skill_split(job: JobView, candidate: CandidateProfile):
    matched, missing, unknown = [], [], []
    for skill in job.skills:
        if skill.name in candidate.skills:
            matched.append(skill)
        elif skill.is_uncertain:
            unknown.append(skill)  # we do not know if it is needed, so it is not "missing"
        else:
            missing.append(skill)
    return matched, missing, unknown


def skills_component(job: JobView, candidate: CandidateProfile) -> Component:
    matched, missing, _ = _skill_split(job, candidate)
    num = sum(SKILL_WEIGHTS[s.requirement_type] for s in matched)
    den = num + sum(SKILL_WEIGHTS[s.requirement_type] for s in missing)
    if den == 0:
        return Component(None, "No clearly stated skills to compare.")
    return Component(100 * num / den, f"{len(matched)} matched, {len(missing)} missing (required skills count 3x).")


def experience_component(job: JobView, candidate: CandidateProfile) -> Component:
    parts, notes = [], []
    if job.min_years is not None and candidate.total_years is not None:
        fit = 100.0 if job.min_years == 0 else min(100.0, 100 * candidate.total_years / job.min_years)
        parts.append(fit)
        notes.append(f"about {candidate.total_years:g} years of experience vs {job.min_years}+ asked"
                     + (" (the posting is unclear)" if job.years_uncertain else ""))
    matched, missing, _ = _skill_split(job, candidate)
    den = sum(SKILL_WEIGHTS[s.requirement_type] for s in matched + missing)
    if den and candidate.has_experience_evidence:
        applied = [s for s in matched + missing if s.name in candidate.applied_skills]
        parts.append(100 * sum(SKILL_WEIGHTS[s.requirement_type] for s in applied) / den)
        notes.append(f"{len(applied)} of {len(matched) + len(missing)} job skills appear in your experience or projects")
    if not parts:
        return Component(None, "Not enough information (no stated years and no skills to compare).")
    return Component(sum(parts) / len(parts), "; ".join(notes) + ".")


# ---------- title ----------

_TITLE_NOISE = {"senior", "sr", "junior", "jr", "lead", "principal", "staff", "associate", "graduate", "mid",
                "level", "intern", "trainee", "remote", "hybrid", "onsite", "m", "f", "d", "w", "x", "i", "ii", "iii"}
_TITLE_SYNONYMS = {"engineer": "developer", "programmer": "developer", "dev": "developer"}


def title_key(title: str) -> str:
    text = (title.lower().replace("c#", "csharp").replace("asp.net", "aspnet").replace(".net", "dotnet")
            .replace("node.js", "nodejs"))
    tokens = [_TITLE_SYNONYMS.get(t, t) for t in re.sub(r"[^a-z0-9]+", " ", text).split() if t not in _TITLE_NOISE]
    return " ".join(tokens) or "developer"


def title_similarity(a: str, b: str) -> float:
    ka, kb = title_key(a), title_key(b)
    return 0.6 * fuzz.token_set_ratio(ka, kb) + 0.4 * fuzz.token_sort_ratio(ka, kb)


def title_component(job: JobView, preferences: Preferences) -> Component:
    if not preferences.job_titles:
        return Component(None, "You have not set any target job titles.")
    best = max(preferences.job_titles, key=lambda t: title_similarity(job.title, t))
    return Component(title_similarity(job.title, best), f"Closest to your target title '{best}'.")


# ---------- seniority ----------

def _derived_levels(years: float | None) -> list[str]:
    if years is None:
        return []
    if years <= 1:
        return ["graduate", "junior"]
    if years <= 3:
        return ["junior", "associate"]
    if years <= 5:
        return ["associate", "mid"]
    return ["mid", "senior"]


def seniority_component(job: JobView, candidate: CandidateProfile, preferences: Preferences) -> Component:
    if job.experience_level not in LEVEL_RANK:
        return Component(None, "The job does not state a level.")
    accepted = preferences.experience_levels or _derived_levels(candidate.total_years)
    accepted = [lvl for lvl in accepted if lvl in LEVEL_RANK]
    if not accepted:
        return Component(None, "No preferred levels set and no experience dates to estimate your level.")
    distance = min(abs(LEVEL_RANK[job.experience_level] - LEVEL_RANK[lvl]) for lvl in accepted)
    score = {0: 100.0, 1: 60.0, 2: 30.0}.get(distance, 0.0)
    return Component(score, f"Job level '{job.experience_level}' vs your levels {', '.join(accepted)}.")


# ---------- location and remote eligibility ----------

def remote_eligibility(job: JobView, countries: set[str]) -> tuple[str, str]:
    """(status, reason) for a remote job. Explicit rules only; unknown stays uncertain."""
    kind, listed = job.remote_eligibility, job.eligible_countries or []
    where = ", ".join(sorted(countries))
    if kind == "worldwide":
        return "eligible", "Open to applicants worldwide."
    if kind == "apac":
        allowed = REGIONS["APAC"]
        if countries & allowed:
            return "eligible", "Open to APAC, and you are in APAC."
        reason = f"Open to APAC only, and you are in {where}."
        return ("ineligible", reason) if countries <= KNOWN_COUNTRIES else ("uncertain", reason)
    if kind in ("country_specific", "region_specific"):
        allowed = set()
        for token in listed:
            allowed |= REGIONS.get(token, {token})
        if countries & allowed:
            return "eligible", f"Open to {', '.join(listed)}, which includes your location."
        known = all(t in REGIONS or len(t) == 2 for t in listed)
        reason = f"Restricted to {', '.join(listed)}; you are in {where}."
        return ("ineligible", reason) if known and (kind == "country_specific" or countries <= KNOWN_COUNTRIES) \
            else ("uncertain", reason)
    return "uncertain", "The listing does not say who may apply from your country."


def location_component(job: JobView, preferences: Preferences) -> tuple[Component, LocationResult]:
    countries = {c.upper() for c in preferences.candidate_countries}
    allowed_arrangements = preferences.work_arrangements or ALL_ARRANGEMENTS
    arrangement = job.work_arrangement

    if not countries:
        result = LocationResult(None, "not_assessed", ["Set the countries you can work in (Settings)."])
    elif arrangement not in ALL_ARRANGEMENTS:
        result = LocationResult(None, "uncertain", ["The listing does not say if the job is remote, hybrid or on-site."])
    elif arrangement == "remote":
        status, reason = remote_eligibility(job, countries)
        entries = preferences.target_locations
        wanted = arrangement in allowed_arrangements and (
            not entries or any("remote" in (e.get("arrangements") or ALL_ARRANGEMENTS) for e in entries))
        score = {"eligible": 100.0, "uncertain": 50.0, "ineligible": 0.0}[status] if wanted else 0.0
        reasons = [reason] + ([] if wanted else ["Remote work is not in your preferences."])
        result = LocationResult(score, status, reasons)
    else:  # hybrid or on-site: must be physically in a country the candidate can work in
        if not job.country_code:
            result = LocationResult(None, "uncertain", [f"The {arrangement} job's country is not stated."])
        elif job.country_code not in countries:
            result = LocationResult(0.0, "ineligible", [
                f"{arrangement.capitalize()} job in {job.country_code}; you can work in {', '.join(sorted(countries))}."])
        else:
            entries = [e for e in preferences.target_locations
                       if (e.get("country_code") or "").upper() == job.country_code
                       and arrangement in (e.get("arrangements") or ALL_ARRANGEMENTS)]
            if arrangement not in allowed_arrangements or (preferences.target_locations and not entries):
                result = LocationResult(0.0, "eligible", [
                    f"{arrangement.capitalize()} work in {job.country_code} is not in your preferred locations."])
            else:
                text = (job.location_text or "").lower()
                exact = not entries or any(not e.get("city") or e["city"].lower() in text for e in entries)
                result = LocationResult(100.0 if exact else 60.0, "eligible", [
                    "Matches your preferred location." if exact else
                    f"In {job.country_code}, but not in your preferred city."])
    return Component(result.score, "; ".join(result.reasons)), result


# ---------- putting it together ----------

def score_job(job: JobView, candidate: CandidateProfile, preferences: Preferences) -> MatchResult:
    location_comp, location = location_component(job, preferences)
    components = {
        "skills": skills_component(job, candidate),
        "experience": experience_component(job, candidate),
        "title": title_component(job, preferences),
        "seniority": seniority_component(job, candidate, preferences),
        "location": location_comp,
    }
    weights = {k: max(float(preferences.weights.get(k, 0)), 0.0) for k in COMPONENTS}
    total = sum(weights.values())
    assessed = sum(weights[k] for k, c in components.items() if c.score is not None)
    overall = (sum(weights[k] * c.score for k, c in components.items() if c.score is not None) / assessed
               if assessed else 0.0)
    coverage = 100 * assessed / total if total else 0.0

    matched, missing, unknown = _skill_split(job, candidate)
    uncertain = [f"{s.name} (mentioned, requirement level unclear)" for s in unknown]
    if location.status == "uncertain":
        uncertain.extend(location.reasons)
    if job.years_uncertain and job.min_years is not None:
        uncertain.append("Years of experience required are stated unclearly.")

    result = MatchResult(
        overall=round(overall, 1), coverage=round(coverage, 1), components=components,
        eligibility_status=location.status, matched_skills=[s.name for s in matched],
        missing_skills=[s.name for s in missing], uncertain_requirements=uncertain,
        location_reasons=location.reasons,
    )
    result.explanation = build_explanation(result, weights)
    return result


def build_explanation(result: MatchResult, weights: dict[str, float]) -> str:
    total = sum(weights.values()) or 1
    lines = []
    for name in COMPONENTS:
        comp = result.components[name]
        share = round(100 * weights[name] / total)
        if comp.score is None:
            lines.append(f"{name.capitalize()} (weight {share}%): not assessed. {comp.detail}")
        else:
            lines.append(f"{name.capitalize()} (weight {share}%): {comp.score:.0f}/100. {comp.detail}")
    lines.append(f"Eligibility: {result.eligibility_status}. {' '.join(result.location_reasons)}".strip())
    lines.append(f"The score uses {result.coverage:.0f}% of the criteria. It is an estimate of fit, "
                 "not a probability of being hired.")
    return "\n".join(lines)