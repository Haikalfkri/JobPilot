from rest_framework import serializers

from .models import FactCategory, MasterResume, ResumeFact, VerificationStatus


class MasterResumeSerializer(serializers.ModelSerializer):
    # Never expose storage_path or extracted_text: no server paths, and less personal data in transit.
    filename = serializers.CharField(source="original_filename", read_only=True)
    fact_counts = serializers.SerializerMethodField()

    class Meta:
        model = MasterResume
        fields = ["id", "filename", "version_number", "file_type", "sha256", "parsing_status",
                  "parsing_error", "is_active", "uploaded_at", "fact_counts"]
        read_only_fields = fields

    def get_fact_counts(self, obj) -> dict:
        counts = {status: 0 for status in VerificationStatus.values}
        for fact_status in obj.facts.values_list("verification_status", flat=True):
            counts[fact_status] += 1
        return counts


class ResumeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class ResumeFactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumeFact
        fields = ["id", "master_resume", "category", "fact_key", "content", "structured_value",
                  "source_location", "verification_status", "created_at", "updated_at"]
        read_only_fields = fields


class FactUpdateSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=False, max_length=5000)
    structured_value = serializers.JSONField(required=False, allow_null=True)
    verification_status = serializers.ChoiceField(
        required=False, choices=[VerificationStatus.USER_CONFIRMED, VerificationStatus.REJECTED]
    )


class FactCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=FactCategory.choices)
    content = serializers.CharField(allow_blank=False, max_length=5000)
    fact_key = serializers.CharField(required=False, allow_blank=True, max_length=50)
    structured_value = serializers.JSONField(required=False, allow_null=True)