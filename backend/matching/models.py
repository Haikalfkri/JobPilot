import uuid

from django.db import models


def default_weights() -> dict:
    return {"skills": 35, "experience": 25, "title": 15, "seniority": 15, "location": 10}


class SearchPreference(models.Model):
    """The user's editable search profile. There is a single row (the 'default' profile)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="default")
    job_titles = models.JSONField(default=list)
    keywords = models.JSONField(default=list)  # used as discovery keywords
    # [{"label": "Batam, Indonesia", "country_code": "ID", "city": "Batam", "arrangements": ["onsite", ...]}]
    target_locations = models.JSONField(default=list)
    work_arrangements = models.JSONField(default=list)
    employment_types = models.JSONField(default=list)
    experience_levels = models.JSONField(default=list)
    # Countries where the candidate can legally work. Remote eligibility is judged against these, never guessed.
    candidate_countries = models.JSONField(default=list)
    component_weights = models.JSONField(default=default_weights)
    minimum_match_score = models.PositiveSmallIntegerField(default=50)
    publication_window_days = models.PositiveSmallIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RequirementType(models.TextChoices):
    REQUIRED = "required"
    PREFERRED = "preferred"
    OPTIONAL = "optional"  # mentioned without saying whether it is needed


class JobRequirements(models.Model):
    """Result of requirement extraction for one job, versioned so results are reproducible."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField("jobs.Job", on_delete=models.CASCADE, related_name="requirements")
    extraction_version = models.CharField(max_length=20)
    description_hash = models.CharField(max_length=64)  # of the description this was extracted from
    min_years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    years_uncertain = models.BooleanField(default=False)
    extracted_at = models.DateTimeField(auto_now=True)


class JobSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="skills")
    skill_name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100)
    requirement_type = models.CharField(max_length=10, choices=RequirementType.choices)
    importance = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    is_uncertain = models.BooleanField(default=False)  # requirement level could not be determined

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "normalized_name"], name="unique_job_skill")]
        ordering = ["requirement_type", "skill_name"]


class EligibilityStatus(models.TextChoices):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNCERTAIN = "uncertain"
    NOT_ASSESSED = "not_assessed"


class JobMatch(models.Model):
    """One current, explainable match result per (job, resume). Component scores are null when not assessable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="matches")
    master_resume = models.ForeignKey("resumes.MasterResume", on_delete=models.CASCADE, related_name="matches")
    scoring_version = models.CharField(max_length=20)
    overall_score = models.DecimalField(max_digits=5, decimal_places=1)
    coverage = models.DecimalField(max_digits=5, decimal_places=1)  # % of the weights that could be assessed
    skill_score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    experience_score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    title_score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    seniority_score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    location_score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    eligibility_status = models.CharField(max_length=15, choices=EligibilityStatus.choices)
    matched_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    uncertain_requirements = models.JSONField(default=list)
    explanation = models.TextField(blank=True, default="")
    details = models.JSONField(default=dict)  # weights, inputs and reasons used for this result
    inputs_hash = models.CharField(max_length=64)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "master_resume"], name="one_match_per_job_resume")]
        indexes = [models.Index(fields=["master_resume", "overall_score"])]
        ordering = ["-overall_score"]