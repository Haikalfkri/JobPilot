from datetime import timedelta
from unittest import mock

import pytest
from django.test import Client
from django.utils import timezone

from core.exceptions import InvalidWorkflow
from jobs.models import Job
from resumes.models import FactCategory, MasterResume, ResumeFact, VerificationStatus

from . import services
from .candidate import CandidateProfile, build_candidate_profile, estimate_years
from .extraction import extract_requirements, extract_skills, extract_years, needs_extraction
from .models import JobMatch, SearchPreference
from .scoring import (
    JobView, Preferences, SkillReq, experience_component, location_component, score_job, seniority_component,
    skills_component, title_component, title_similarity,
)
from .skills import expand_with_implied, find_skills
from .tasks import analyze_job_task, refresh_matches_task

# ---------- builders ----------

def jv(**kw):
    base = dict(title="Python Developer", work_arrangement="remote", remote_eligibility="worldwide",
                eligible_countries=None, country_code=None, location_text=None, experience_level="junior",
                skills=[], min_years=None, years_uncertain=False)
    return JobView(**{**base, **kw})


def prefs(**kw):
    base = dict(job_titles=["Python Developer"], target_locations=[], work_arrangements=["remote", "hybrid", "onsite"],
                experience_levels=["graduate", "junior", "associate"], candidate_countries=["ID"],
                weights={"skills": 35, "experience": 25, "title": 15, "seniority": 15, "location": 10})
    return Preferences(**{**base, **kw})


def cand(**kw):
    base = dict(resume_id="r", skills={"Python", "Django"}, applied_skills={"Python", "Django"}, total_years=3.0,
                has_experience_evidence=True, fact_count=5, fingerprint="x")
    return CandidateProfile(**{**base, **kw})


def req(name, rtype="required", uncertain=False):
    return SkillReq(name, rtype, uncertain)


# ---------- skills ----------

def test_skill_detection_respects_word_boundaries():
    assert find_skills("Python, Django and PostgreSQL") == ["Python", "Django", "PostgreSQL"]
    assert find_skills("ASP.NET Core and .NET 8 with C#") == ["ASP.NET Core", ".NET", "C#"]
    assert find_skills("JavaScript and Java, SQL, NoSQL, MySQL") == ["JavaScript", "Java", "SQL", "MySQL"]
    assert find_skills("Node.js, CI/CD, k8s, GitHub Actions") == ["Node.js", "CI/CD", "Kubernetes", "GitHub Actions"]
    assert find_skills("We will go to the office") == []  # "go" alone is not a skill
    assert find_skills("Experience with C++ and C#.") == ["C++", "C#"]


def test_implied_skills_only_expand_the_candidate_side():
    assert expand_with_implied({"Django"}) == {"Django", "Python"}
    assert expand_with_implied({"ASP.NET Core"}) == {"ASP.NET Core", ".NET", "C#"}
    assert expand_with_implied({"Python"}) == {"Python"}


# ---------- requirement extraction ----------

DESCRIPTION = """About us
We build APIs with Python and Django.

Requirements:
- 3+ years of professional experience
- Strong PostgreSQL knowledge
- Docker

Nice to have:
- Redis
- AWS

Bonus points for Kubernetes
We use Celery daily."""


def test_sections_and_cues_decide_required_vs_preferred_and_uncertain():
    found = extract_skills("Senior Python Developer", DESCRIPTION)
    assert found["Python"] == ("required", False)  # in the title
    assert found["PostgreSQL"] == ("required", False) and found["Docker"] == ("required", False)
    assert found["Redis"] == ("preferred", False) and found["AWS"] == ("preferred", False)
    assert found["Kubernetes"] == ("preferred", False)  # line cue, no heading
    assert found["Django"] == ("optional", True)  # mentioned under "About us": level unclear
    assert found["Celery"] == ("optional", True)  # the "Nice to have" section ended at the blank line


@pytest.mark.parametrize("text,expected", [
    ("3+ years of professional experience", (3, False)),
    ("2-4 years experience", (2, False)),
    ("5 years of Python experience", (5, True)),  # per-skill years: uncertain
    ("3+ years of relevant work experience and 5 years of professional experience", (3, True)),
    ("Great culture and snacks", (None, False)),
])
def test_years_of_experience(text, expected):
    assert extract_years(text) == expected


def make_job(**kw):
    defaults = dict(title="Python Developer", normalized_title="python developer", company_name="Acme",
                    description="", discovered_at=timezone.now(), status="active", description_hash="h",
                    work_arrangement="remote", remote_eligibility="worldwide", experience_level="junior")
    return Job.objects.create(**{**defaults, **kw})


@pytest.mark.django_db
def test_extraction_is_versioned_and_reruns_when_the_description_changes():
    job = make_job(description=DESCRIPTION, description_hash="v1")
    requirements = extract_requirements(job)
    assert requirements.extraction_version == "v1" and requirements.min_years_experience == 3
    assert job.skills.get(normalized_name="redis").requirement_type == "preferred"
    job = Job.objects.get(pk=job.pk)
    assert needs_extraction(job) is False
    job.description_hash = "v2"
    assert needs_extraction(job) is True


# ---------- candidate profile ----------

def make_resume(facts, active=True):
    resume = MasterResume.objects.create(version_number=(MasterResume.objects.count() + 1),
                                         original_filename="cv.pdf", storage_path="x", file_type="pdf",
                                         sha256="s" * 64, parsing_status="completed", is_active=active)
    for position, (category, content, status) in enumerate(facts):
        ResumeFact.objects.create(master_resume=resume, category=category, content=content,
                                  verification_status=status, position=position)
    return resume


CONFIRMED = VerificationStatus.USER_CONFIRMED

FACTS = [
    (FactCategory.SKILL, "Python", CONFIRMED), (FactCategory.SKILL, "Django", CONFIRMED),
    (FactCategory.SKILL, "PostgreSQL", CONFIRMED), (FactCategory.SKILL, "Docker", CONFIRMED),
    (FactCategory.EXPERIENCE, "Acme Corp - Backend Developer (2022 - 2025)", CONFIRMED),
    (FactCategory.EXPERIENCE, "Built Django APIs backed by PostgreSQL", CONFIRMED),
    (FactCategory.EDUCATION, "B.Sc. Computer Science (2018 - 2022)", CONFIRMED),
    (FactCategory.SKILL, "AWS", VerificationStatus.PARSER_SUGGESTED),  # never counted
    (FactCategory.SKILL, "Kubernetes", VerificationStatus.REJECTED),  # never counted
]


def test_year_ranges_are_merged_not_double_counted():
    year = timezone.now().year
    assert estimate_years(["A (2019 - 2021)", "B (Jan 2020 - Present)"]) == year - 2019
    assert estimate_years(["no dates here"]) is None


@pytest.mark.django_db
def test_candidate_profile_uses_only_confirmed_facts():
    profile = build_candidate_profile(make_resume(FACTS))
    assert profile.fact_count == 7
    assert {"Python", "Django", "PostgreSQL", "Docker", "SQL"} <= profile.skills
    assert "AWS" not in profile.skills and "Kubernetes" not in profile.skills
    assert profile.applied_skills == {"Django", "PostgreSQL", "Python", "SQL"}  # evidenced in experience
    assert profile.total_years == 3.0  # education years are not work experience
    assert profile.has_experience_evidence and "SQL" in profile.implied_skills


# ---------- scoring components ----------

def test_skills_component_weights_required_more_and_keeps_unknown_separate():
    job = jv(skills=[req("Python"), req("Django"), req("Docker", "preferred"), req("AWS", "preferred"),
                     req("Redis", "optional", True)])
    # matched: Python 3 + Django 3 ; missing: Docker 1 + AWS 1 ; Redis is unknown, not missing
    assert skills_component(job, cand()).score == pytest.approx(100 * 6 / 8)
    # an unknown skill the candidate DOES have counts as a match (weight 1)
    assert skills_component(job, cand(skills={"Python", "Django", "Redis"})).score == pytest.approx(100 * 7 / 9)
    assert skills_component(jv(skills=[req("Redis", "optional", True)]), cand()).score is None
    assert skills_component(jv(skills=[]), cand()).score is None


def test_experience_component_combines_years_and_applied_skills():
    job = jv(skills=[req("Python"), req("Docker", "preferred")], min_years=6)
    c = cand(skills={"Python", "Docker"}, applied_skills={"Python"}, total_years=3.0)
    assert experience_component(job, c).score == pytest.approx((50 + 75) / 2)  # 3/6 years ; Python 3 of 4
    assert experience_component(jv(), cand()).score is None  # nothing to compare
    assert experience_component(jv(min_years=2), cand(total_years=None)).score is None


def test_title_component_ignores_seniority_words_and_uses_user_titles():
    assert title_similarity("Senior Python Developer (m/f/d)", "Python Developer") == 100
    assert title_similarity("Software Engineer", "Software Developer") == 100
    assert title_component(jv(title="Marketing Manager"), prefs()).score < 40
    assert title_component(jv(), prefs(job_titles=[])).score is None


@pytest.mark.parametrize("job_level,expected", [
    ("junior", 100), ("associate", 100), ("mid", 60), ("senior", 30), ("unknown", None)])
def test_seniority_distance_from_preferred_levels(job_level, expected):
    assert seniority_component(jv(experience_level=job_level), cand(), prefs()).score == expected


def test_seniority_falls_back_to_candidate_years_when_no_levels_are_set():
    assert seniority_component(jv(experience_level="junior"), cand(total_years=2.0),
                               prefs(experience_levels=[])).score == 100
    assert seniority_component(jv(experience_level="senior"), cand(total_years=None),
                               prefs(experience_levels=[])).score is None


BATAM = {"label": "Batam", "country_code": "ID", "city": "Batam", "arrangements": ["onsite", "hybrid", "remote"]}


@pytest.mark.parametrize("job_kw,pref_kw,status,score", [
    (dict(remote_eligibility="worldwide"), {}, "eligible", 100),
    (dict(remote_eligibility="apac"), {}, "eligible", 100),
    (dict(remote_eligibility="apac"), dict(candidate_countries=["US"]), "ineligible", 0),
    (dict(remote_eligibility="country_specific", eligible_countries=["US"]), {}, "ineligible", 0),
    (dict(remote_eligibility="country_specific", eligible_countries=["US", "ID"]), {}, "eligible", 100),
    (dict(remote_eligibility="region_specific", eligible_countries=["EUROPE"]), {}, "ineligible", 0),
    (dict(remote_eligibility="region_specific", eligible_countries=["APAC", "US"]), {}, "eligible", 100),
    (dict(remote_eligibility="region_specific", eligible_countries=["EUROPE"]), dict(candidate_countries=["KE"]),
     "uncertain", 50),  # an unfamiliar country: do not claim ineligible
    (dict(remote_eligibility="unknown"), {}, "uncertain", 50),
    (dict(remote_eligibility="worldwide"), dict(work_arrangements=["onsite"]), "eligible", 0),
    (dict(work_arrangement="unknown", remote_eligibility="unknown"), {}, "uncertain", None),
    (dict(remote_eligibility="worldwide"), dict(candidate_countries=[]), "not_assessed", None),
])
def test_remote_eligibility_rules(job_kw, pref_kw, status, score):
    _, result = location_component(jv(**job_kw), prefs(**pref_kw))
    assert result.status == status and result.score == score


@pytest.mark.parametrize("job_kw,status,score", [
    (dict(work_arrangement="onsite", country_code="ID", location_text="Batam, Indonesia"), "eligible", 100),
    (dict(work_arrangement="hybrid", country_code="ID", location_text="Jakarta, Indonesia"), "eligible", 60),
    (dict(work_arrangement="onsite", country_code="SG", location_text="Singapore"), "ineligible", 0),
    (dict(work_arrangement="onsite", country_code=None, location_text="Somewhere"), "uncertain", None),
])
def test_onsite_and_hybrid_need_a_country_the_candidate_can_work_in(job_kw, status, score):
    _, result = location_component(jv(**job_kw), prefs(target_locations=[BATAM]))
    assert result.status == status and result.score == score


def test_overall_score_averages_only_assessed_components_and_reports_coverage():
    job = jv(skills=[req("Python"), req("Django")], experience_level="unknown", remote_eligibility="unknown")
    result = score_job(job, cand(), prefs())
    # skills 100 (35), experience 100 via applied skills (25), title 100 (15), seniority n/a, location 50 (10)
    assert result.components["seniority"].score is None
    assert result.overall == pytest.approx((35 * 100 + 25 * 100 + 15 * 100 + 10 * 50) / 85, abs=0.1)
    assert result.coverage == pytest.approx(85.0)
    assert result.eligibility_status == "uncertain" and result.uncertain_requirements
    assert "not assessed" in result.explanation and "not a probability" in result.explanation


def test_nothing_assessable_gives_zero_with_zero_coverage():
    job = jv(title="Python Developer", experience_level="unknown", work_arrangement="unknown", skills=[])
    result = score_job(job, cand(total_years=None, has_experience_evidence=False),
                       prefs(job_titles=[], candidate_countries=[]))
    assert result.overall == 0.0 and result.coverage == 0.0


def test_scoring_is_repeatable_and_weights_are_configurable():
    job = jv(skills=[req("Python"), req("Java")], title="Java Developer")
    a, b = score_job(job, cand(), prefs()), score_job(job, cand(), prefs())
    assert a.overall == b.overall and a.explanation == b.explanation
    skills_only = score_job(job, cand(), prefs(weights={"skills": 1, "experience": 0, "title": 0,
                                                       "seniority": 0, "location": 0}))
    assert skills_only.overall == pytest.approx(a.components["skills"].score, abs=0.1)


# ---------- end to end: confirmed facts + jobs -> explainable results ----------

JOB_A = """Requirements:
- 2+ years of professional experience
- Python and Django
- PostgreSQL

Nice to have:
- AWS
- Docker

We offer remote work."""

JOB_B = """Requirements:
- 5+ years of experience
- Java and Spring Boot"""


@pytest.fixture
def scenario(db):
    resume = make_resume(FACTS)
    job_a = make_job(title="Python Developer", description=JOB_A, description_hash="a", experience_level="junior")
    job_b = make_job(title="Senior Java Developer", description=JOB_B, description_hash="b", company_name="Globex",
                     experience_level="senior", remote_eligibility="country_specific", eligible_countries=["US"])
    return resume, job_a, job_b


def test_known_resume_and_jobs_give_explainable_repeatable_results(scenario):
    resume, job_a, job_b = scenario
    first = services.refresh_matches()
    assert first == {"scored": 2, "skipped": 0, "failed": 0}
    a = JobMatch.objects.get(job=job_a)
    b = JobMatch.objects.get(job=job_b)

    assert set(a.matched_skills) == {"Python", "Django", "PostgreSQL", "Docker"}
    assert a.missing_skills == ["AWS"] and a.eligibility_status == "eligible"
    assert float(a.skill_score) == pytest.approx(100 * 10 / 11, abs=0.1)  # 3 required*3 + Docker 1 of 11
    assert float(a.experience_score) == pytest.approx((100 + 100 * 9 / 11) / 2, abs=0.1)
    assert float(a.title_score) == 100 and float(a.seniority_score) == 100 and float(a.location_score) == 100
    assert float(a.overall_score) == pytest.approx(94.5, abs=0.1) and float(a.coverage) == 100
    assert "Skills (weight 35%)" in a.explanation and a.details["candidate"]["confirmed_facts"] == 7

    # B is ineligible (US only) but its score is still computed: eligibility is flagged independently
    assert b.eligibility_status == "ineligible" and float(b.location_score) == 0
    assert set(b.missing_skills) == {"Java", "Spring Boot"} and float(b.overall_score) < float(a.overall_score)

    # nothing changed: the second run recalculates nothing, and the stored results are identical
    assert services.refresh_matches() == {"scored": 0, "skipped": 2, "failed": 0}
    assert float(JobMatch.objects.get(job=job_a).overall_score) == float(a.overall_score)


def test_changing_preferences_or_facts_or_description_recalculates(scenario):
    resume, job_a, _ = scenario
    services.refresh_matches()

    pref = services.get_preferences()
    pref.component_weights = {"skills": 100, "experience": 0, "title": 0, "seniority": 0, "location": 0}
    pref.save()
    assert services.refresh_matches()["scored"] == 2

    ResumeFact.objects.create(master_resume=resume, category="skill", content="AWS", verification_status=CONFIRMED)
    assert services.refresh_matches()["scored"] == 2
    assert JobMatch.objects.get(job=job_a).missing_skills == []

    job_a.description = JOB_A + "\n\nRequirements:\n- Kafka"
    job_a.description_hash = "a2"
    job_a.save()
    assert services.refresh_matches()["scored"] == 1  # only the changed job, re-extracted
    assert "Kafka" in JobMatch.objects.get(job=job_a).missing_skills


def test_closed_jobs_are_not_scored(scenario):
    _, job_a, _ = scenario
    job_a.status = "closed"
    job_a.save()
    assert services.refresh_matches()["scored"] == 1


@pytest.mark.django_db
def test_matching_needs_an_active_resume_with_confirmed_facts():
    with pytest.raises(InvalidWorkflow):
        services.refresh_matches()
    make_resume([(FactCategory.SKILL, "Python", VerificationStatus.PARSER_SUGGESTED)])
    with pytest.raises(InvalidWorkflow):
        services.refresh_matches()


# ---------- API ----------

@pytest.fixture
def client():
    return Client()


def put_json(client, url, body):
    return client.put(url, body, content_type="application/json")


@pytest.mark.django_db
def test_preferences_start_from_your_search_profile_and_can_be_edited(client):
    data = client.get("/api/v1/settings/search-preferences/").json()
    assert "Python Developer" in data["job_titles"] and data["candidate_countries"] == ["ID"]
    assert data["component_weights"] == {"skills": 35, "experience": 25, "title": 15, "seniority": 15, "location": 10}
    assert data["target_locations"][0]["city"] == "Batam"

    with mock.patch.object(refresh_matches_task, "delay") as queued:
        response = put_json(client, "/api/v1/settings/search-preferences/", {
            "job_titles": ["  Backend Developer ", "Backend Developer", "Go Developer"],
            "candidate_countries": ["id", "sg"], "minimum_match_score": 70,
            "target_locations": [{"label": "Batam", "country_code": "id", "city": " Batam "}],
        })
    assert response.status_code == 200
    saved = response.json()
    assert saved["job_titles"] == ["Backend Developer", "Go Developer"]
    assert saved["candidate_countries"] == ["ID", "SG"] and saved["minimum_match_score"] == 70
    assert saved["target_locations"][0] == {"label": "Batam", "country_code": "ID", "city": "Batam",
                                            "arrangements": ["remote", "hybrid", "onsite"]}
    queued.assert_called_once()
    assert SearchPreference.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("body", [
    {"component_weights": {"skills": 0, "experience": 0, "title": 0, "seniority": 0, "location": 0}},
    {"component_weights": {"skills": 50}},
    {"work_arrangements": ["office"]},
    {"minimum_match_score": 120},
    {"candidate_countries": ["Indonesia"]},
])
def test_invalid_preferences_are_rejected(client, body):
    response = put_json(client, "/api/v1/settings/search-preferences/", body)
    assert response.status_code == 400 and response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_analyze_and_recalculate_need_a_usable_resume_and_queue_work(client, scenario):
    resume, job_a, _ = scenario
    resume.is_active = False
    resume.save()
    blocked = client.post(f"/api/v1/matching/jobs/{job_a.id}/analyze/")
    assert blocked.status_code == 422 and blocked.json()["error"]["code"] == "INVALID_WORKFLOW"
    assert client.post("/api/v1/matching/recalculate/").status_code == 422

    resume.is_active = True
    resume.save()
    with mock.patch.object(analyze_job_task, "delay") as one, mock.patch.object(refresh_matches_task, "delay") as many:
        assert client.post(f"/api/v1/matching/jobs/{job_a.id}/analyze/").status_code == 202
        assert client.post("/api/v1/matching/recalculate/").status_code == 202
    one.assert_called_once_with(str(job_a.id), True)
    many.assert_called_once_with(True)
    assert client.post("/api/v1/matching/jobs/00000000-0000-0000-0000-000000000000/analyze/").status_code == 404


@pytest.mark.django_db
def test_result_endpoints_match_the_api_guide_shape(client, scenario):
    _, job_a, job_b = scenario
    services.refresh_matches()
    listing = client.get("/api/v1/matching/results/").json()
    assert listing["count"] == 2 and listing["results"][0]["job_id"] == str(job_a.id)  # best first
    top = listing["results"][0]
    assert set(top) >= {"job_id", "overall_score", "components", "eligibility_status", "matched_skills",
                        "missing_skills", "uncertain_requirements", "scoring_version"}
    assert set(top["components"]) == {"skills", "experience", "title", "seniority", "location"}
    assert top["scoring_version"] == "v1" and isinstance(top["overall_score"], float)

    only_eligible = client.get("/api/v1/matching/results/?eligibility_status=eligible").json()
    assert [r["job_id"] for r in only_eligible["results"]] == [str(job_a.id)]
    assert client.get(f"/api/v1/matching/results/?job_id={job_b.id}").json()["count"] == 1
    assert client.get("/api/v1/matching/results/?min_score=99").json()["count"] == 0

    detail = client.get(f"/api/v1/matching/results/{top['id']}/").json()
    assert "Skills (weight 35%)" in detail["explanation"] and detail["details"]["weights"]["skills"] == 35


@pytest.mark.django_db
def test_job_list_can_filter_and_sort_by_match(client, scenario):
    _, job_a, job_b = scenario
    make_job(title="Unscored Role", company_name="Initech", description_hash="c")
    services.refresh_matches(job_ids=[job_a.id, job_b.id])

    def titles(query):
        return [j["title"] for j in client.get(f"/api/v1/jobs/?{query}").json()["results"]]

    assert titles("ordering=-match_score")[:2] == ["Python Developer", "Senior Java Developer"]
    assert titles("ordering=-match_score")[-1] == "Unscored Role"  # unscored jobs sort last
    assert titles("min_match_score=90") == ["Python Developer"]
    assert "Senior Java Developer" not in titles("hide_ineligible=true")
    assert "Unscored Role" in titles("hide_ineligible=true")  # unknown is not ineligible
    assert titles("eligibility_status=ineligible") == ["Senior Java Developer"]
    first = client.get("/api/v1/jobs/?ordering=-match_score").json()["results"][0]
    assert first["match_score"] > 90 and first["match_eligibility"] == "eligible"
    assert client.get("/api/v1/jobs/?min_match_score=200").status_code == 400


@pytest.mark.django_db
def test_only_the_active_resume_drives_job_scores(client, scenario):
    resume, job_a, _ = scenario
    services.refresh_matches()
    resume.is_active = False
    resume.save()
    assert client.get("/api/v1/jobs/?ordering=-match_score").json()["results"][0]["match_score"] is None


def test_tasks_swallow_missing_resume_instead_of_failing(db):
    refresh_matches_task()  # no active resume: logged and skipped, no exception
    analyze_job_task("00000000-0000-0000-0000-000000000000")


# ---------- integration with resume activation ----------

@pytest.mark.django_db
def test_activating_a_resume_queues_a_match_refresh(task_bus):
    from resumes.services import activate_resume

    resume = make_resume(FACTS, active=False)
    activate_resume(resume)
    assert any(name == "matching.tasks.refresh_matches_task" for name, _, _ in task_bus)