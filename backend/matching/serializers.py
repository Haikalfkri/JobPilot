from rest_framework import serializers

from jobs.models import WorkArrangement

from .models import EligibilityStatus, JobMatch, SearchPreference
from .scoring import COMPONENTS

ARRANGEMENTS = [c for c in WorkArrangement.values if c != "unknown"]
LEVELS = ["graduate", "junior", "associate", "mid", "senior"]
TYPES = ["full_time", "contract", "internship", "part_time"]


def _float(value):
    return None if value is None else float(value)


class TargetLocationSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100)
    country_code = serializers.RegexField(r"^[A-Za-z]{2}$", required=False, allow_null=True, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    arrangements = serializers.ListField(child=serializers.ChoiceField(choices=ARRANGEMENTS), required=False)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        value["country_code"] = (value.get("country_code") or "").upper() or None
        value["city"] = (value.get("city") or "").strip() or None
        value["arrangements"] = value.get("arrangements") or list(ARRANGEMENTS)
        return value


def _unique(values):
    return list(dict.fromkeys(v.strip() for v in values if v.strip()))


class SearchPreferenceSerializer(serializers.ModelSerializer):
    job_titles = serializers.ListField(child=serializers.CharField(max_length=100), max_length=100, required=False)
    keywords = serializers.ListField(child=serializers.CharField(max_length=50), max_length=50, required=False)
    target_locations = serializers.ListField(child=TargetLocationSerializer(), max_length=30, required=False)
    work_arrangements = serializers.ListField(child=serializers.ChoiceField(choices=ARRANGEMENTS), required=False)
    employment_types = serializers.ListField(child=serializers.ChoiceField(choices=TYPES), required=False)
    experience_levels = serializers.ListField(child=serializers.ChoiceField(choices=LEVELS), required=False)
    candidate_countries = serializers.ListField(
        child=serializers.RegexField(r"^[A-Za-z]{2}$"), max_length=30, required=False)
    component_weights = serializers.DictField(child=serializers.FloatField(min_value=0, max_value=100), required=False)
    minimum_match_score = serializers.IntegerField(min_value=0, max_value=100, required=False)
    publication_window_days = serializers.IntegerField(min_value=1, max_value=365, required=False)

    class Meta:
        model = SearchPreference
        fields = ["job_titles", "keywords", "target_locations", "work_arrangements", "employment_types",
                  "experience_levels", "candidate_countries", "component_weights", "minimum_match_score",
                  "publication_window_days", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_job_titles(self, value):
        return _unique(value)

    def validate_keywords(self, value):
        return _unique(value)

    def validate_candidate_countries(self, value):
        return list(dict.fromkeys(v.upper() for v in value))

    def validate_component_weights(self, value):
        if set(value) != set(COMPONENTS):
            raise serializers.ValidationError(f"Provide exactly these weights: {', '.join(COMPONENTS)}.")
        if sum(value.values()) <= 0:
            raise serializers.ValidationError("At least one weight must be above zero.")
        return value


class MatchSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)
    company_name = serializers.CharField(source="job.company_name", read_only=True)
    overall_score = serializers.SerializerMethodField()
    coverage = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()

    class Meta:
        model = JobMatch
        fields = ["id", "job_id", "job_title", "company_name", "overall_score", "coverage", "components",
                  "eligibility_status", "matched_skills", "missing_skills", "uncertain_requirements",
                  "scoring_version", "calculated_at"]
        read_only_fields = fields

    def get_overall_score(self, match) -> float:
        return _float(match.overall_score)

    def get_coverage(self, match) -> float:
        return _float(match.coverage)

    def get_components(self, match) -> dict:
        return {"skills": _float(match.skill_score), "experience": _float(match.experience_score),
                "title": _float(match.title_score), "seniority": _float(match.seniority_score),
                "location": _float(match.location_score)}


class MatchDetailSerializer(MatchSerializer):
    class Meta(MatchSerializer.Meta):
        fields = MatchSerializer.Meta.fields + ["explanation", "details"]
        read_only_fields = fields


class MatchFilterSerializer(serializers.Serializer):
    job_id = serializers.UUIDField(required=False)
    min_score = serializers.FloatField(required=False, min_value=0, max_value=100)
    eligibility_status = serializers.ChoiceField(required=False, choices=EligibilityStatus.choices)
    ordering = serializers.ChoiceField(required=False, choices=["overall_score", "-overall_score", "-calculated_at"])