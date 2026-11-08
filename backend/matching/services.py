"""Matching workflow: preferences, requirement extraction, scoring and persistence."""
import hashlib
import json
import logging
from decimal import Decimal

from core.exceptions import InvalidWorkflow
from jobs.models import Job, JobStatus
from resumes.models import MasterResume

from .candidate import CandidateProfile, build_candidate_profile
from .extraction import EXTRACTION_VERSION, extract_requirements, needs_extraction
from .models import JobMatch, SearchPreference
from .scoring import SCORING_VERSION, JobView, Preferences, SkillReq, score_job

logger = logging.getLogger(__name__)

DEFAULT_TITLES = [
    "Backend Software Engineer", "Backend Developer", "Software Engineer", "Software Developer",
    "Junior Software Engineer", "Graduate Software Engineer", "Python Developer", "Django Developer",
    "C# Developer", ".NET Developer", "ASP.NET Core Developer", "Full Stack Developer", "Web Developer",
    "API Developer", "Application Developer", "Associate Software Engineer",
]
ALL = ["remote", "hybrid", "onsite"]


def default_preference_values() -> dict:
    return {
        "job_titles": DEFAULT_TITLES,
        "keywords": ["python", "django", "backend", "software engineer", "developer"],
        "target_locations": [
            {"label": "Batam, Indonesia", "country_code": "ID", "city": "Batam", "arrangements": ALL},
            {"label": "Indonesia", "country_code": "ID", "city": None, "arrangements": ["remote"]},
        ],
        "work_arrangements": ALL,
        "employment_types": [],
        "experience_levels": ["graduate", "junior", "associate"],
        "candidate_countries": ["ID"],
    }


def get_preferences() -> SearchPreference:
    prefs = SearchPreference.objects.first()
    return prefs or SearchPreference.objects.create(**default_preference_values())


def preference_snapshot(prefs: SearchPreference) -> dict:
    return {
        "job_titles": prefs.job_titles, "target_locations": prefs.target_locations,
        "work_arrangements": prefs.work_arrangements, "experience_levels": prefs.experience_levels,
        "candidate_countries": prefs.candidate_countries, "weights": prefs.component_weights,
    }


def to_preferences(prefs: SearchPreference) -> Preferences:
    snap = preference_snapshot(prefs)
    return Preferences(**{k: v for k, v in snap.items()})


def require_candidate() -> tuple[MasterResume, CandidateProfile]:
    resume = MasterResume.objects.filter(is_active=True).first()
    if resume is None:
        raise InvalidWorkflow("Activate a master resume first.")
    candidate = build_candidate_profile(resume)
    if candidate.fact_count == 0:
        raise InvalidWorkflow("Confirm at least one resume fact first. Matching only uses confirmed facts.")
    return resume, candidate


def job_view(job: Job) -> JobView:
    requirements = job.requirements
    return JobView(
        title=job.title, work_arrangement=job.work_arrangement, remote_eligibility=job.remote_eligibility,
        eligible_countries=job.eligible_countries, country_code=job.country_code, location_text=job.location_text,
        experience_level=job.experience_level,
        skills=[SkillReq(s.skill_name, s.requirement_type, s.is_uncertain) for s in job.skills.all()],
        min_years=requirements.min_years_experience, years_uncertain=requirements.years_uncertain,
    )


def _inputs_hash(resume, candidate, snapshot, view: JobView, job: Job) -> str:
    payload = {
        "scoring": SCORING_VERSION, "extraction": EXTRACTION_VERSION, "resume": str(resume.id),
        "candidate": candidate.fingerprint, "preferences": snapshot,
        "job": [job.work_arrangement, job.remote_eligibility, job.eligible_countries, job.country_code,
                job.location_text, job.experience_level, job.title, job.requirements.description_hash,
                view.min_years, view.years_uncertain,
                sorted((s.name, s.requirement_type, s.is_uncertain) for s in view.skills)],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 1)))


def analyze_job(job: Job, resume: MasterResume, candidate: CandidateProfile, prefs: SearchPreference,
                force: bool = False) -> tuple[JobMatch, bool]:
    """Returns (match, recalculated). Skips the work when no input changed since the last result."""
    if needs_extraction(job):
        extract_requirements(job)
        job = Job.objects.select_related("requirements").get(pk=job.pk)
    view = job_view(job)
    snapshot = preference_snapshot(prefs)
    inputs_hash = _inputs_hash(resume, candidate, snapshot, view, job)

    existing = JobMatch.objects.filter(job=job, master_resume=resume).first()
    if existing and existing.inputs_hash == inputs_hash and not force:
        return existing, False

    result = score_job(view, candidate, to_preferences(prefs))
    comps = result.components
    match, _ = JobMatch.objects.update_or_create(job=job, master_resume=resume, defaults={
        "scoring_version": SCORING_VERSION, "overall_score": _dec(result.overall), "coverage": _dec(result.coverage),
        "skill_score": _dec(comps["skills"].score), "experience_score": _dec(comps["experience"].score),
        "title_score": _dec(comps["title"].score), "seniority_score": _dec(comps["seniority"].score),
        "location_score": _dec(comps["location"].score), "eligibility_status": result.eligibility_status,
        "matched_skills": result.matched_skills, "missing_skills": result.missing_skills,
        "uncertain_requirements": result.uncertain_requirements, "explanation": result.explanation,
        "inputs_hash": inputs_hash,
        "details": {
            "weights": prefs.component_weights, "extraction_version": EXTRACTION_VERSION,
            "components": {k: {"score": c.score if c.score is None else round(c.score, 1), "detail": c.detail}
                           for k, c in comps.items()},
            "location_reasons": result.location_reasons,
            "candidate": {"confirmed_facts": candidate.fact_count, "estimated_years": candidate.total_years,
                          "implied_skills": sorted(candidate.implied_skills)},
            "preferences": snapshot,
        },
    })
    return match, True


def refresh_matches(job_ids=None, force: bool = False) -> dict:
    """Extract requirements and (re)score jobs against the active resume. Raises InvalidWorkflow without one."""
    resume, candidate = require_candidate()
    prefs = get_preferences()
    jobs = Job.objects.select_related("requirements").exclude(status__in=[JobStatus.CLOSED, JobStatus.EXPIRED])
    if job_ids is not None:
        jobs = jobs.filter(pk__in=job_ids)
    counts = {"scored": 0, "skipped": 0, "failed": 0}
    for job in jobs.iterator():
        try:
            _, recalculated = analyze_job(job, resume, candidate, prefs, force=force)
            counts["scored" if recalculated else "skipped"] += 1
        except Exception:  # noqa: BLE001 - one bad job must not stop the rest
            logger.exception("Could not score job %s", job.pk)
            counts["failed"] += 1
    return counts