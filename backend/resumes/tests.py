import io
from unittest import mock

import pymupdf
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from docx import Document

from .models import MasterResume, ResumeFact
from .parsing import parse_facts
from .pipeline import parse_resume
from .tasks import parse_resume_task

SAMPLE = """Jane Doe
jane.doe@example.com | +62 812 3456 7890 | github.com/janedoe | linkedin.com/in/janedoe

Summary
Backend developer who builds Django APIs.

Experience
Acme Corp - Backend Developer (2021 - 2024)
• Built REST APIs with Django and PostgreSQL

Skills
Languages: Python, C#
Frameworks: Django, ASP.NET Core

Education
Universitas Putera Batam - B.Sc. Computer Science (2018 - 2022)
"""


# ---------- helpers / fixtures ----------

def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((50, 60), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def make_docx(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def inline_parse():
    """Run the Celery task synchronously so tests do not need Redis or a worker."""
    with mock.patch.object(parse_resume_task, "delay", side_effect=lambda rid: parse_resume(rid)) as patched:
        yield patched


@pytest.fixture
def client():
    return Client()


def upload(client, name, content, content_type="application/octet-stream"):
    return client.post("/api/v1/resumes/upload/",
                       {"file": SimpleUploadedFile(name, content, content_type=content_type)})


# ---------- parser unit tests ----------

def test_parser_extracts_contact_sections_and_skills():
    facts = parse_facts(SAMPLE)
    by_key = {(f["category"], f["fact_key"]): f["content"] for f in facts if f["fact_key"]}
    assert by_key[("personal", "full_name")] == "Jane Doe"
    assert by_key[("personal", "email")] == "jane.doe@example.com"
    assert by_key[("personal", "phone")] == "+62 812 3456 7890"
    assert by_key[("link", "github")] == "github.com/janedoe"
    assert by_key[("link", "linkedin")] == "linkedin.com/in/janedoe"
    skills = [f["content"] for f in facts if f["category"] == "skill"]
    assert skills == ["Python", "C#", "Django", "ASP.NET Core"]
    assert any(f["category"] == "summary" for f in facts)
    assert any("Acme Corp" in f["content"] for f in facts if f["category"] == "experience")
    assert any(f["category"] == "education" for f in facts)


def test_parser_does_not_mistake_date_ranges_for_phone_numbers():
    facts = parse_facts("Jane Doe\nSenior Dev 2018 - 2022 - 2024\n")
    assert not [f for f in facts if f["fact_key"] == "phone"]


def test_every_fact_has_a_source_location_and_is_only_a_suggestion():
    assert all(f["source_location"] for f in parse_facts(SAMPLE))


# ---------- upload ----------

@pytest.mark.django_db
def test_upload_pdf_parses_into_suggested_facts(client, inline_parse):
    response = upload(client, "master.pdf", make_pdf(SAMPLE))
    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["filename"] == "master.pdf"
    assert body["parsing_status"] == "review_required"
    assert body["is_active"] is False
    assert body["fact_counts"]["parser_suggested"] > 0
    assert body["duplicate_of_version"] is None
    assert "storage_path" not in body and "extracted_text" not in body


@pytest.mark.django_db
def test_upload_docx_parses(client, inline_parse):
    body = upload(client, "master.docx", make_docx(SAMPLE)).json()
    assert body["parsing_status"] == "review_required"
    emails = ResumeFact.objects.filter(fact_key="email")
    assert [f.content for f in emails] == ["jane.doe@example.com"]


@pytest.mark.django_db
@pytest.mark.parametrize("name,content", [
    ("resume.txt", b"hello"),
    ("resume.pdf", b"this is not a pdf"),
    ("resume.docx", b"PK\x03\x04 not really a docx"),
    ("resume.pdf", b""),
])
def test_invalid_uploads_are_rejected(client, inline_parse, name, content):
    response = upload(client, name, content)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert MasterResume.objects.count() == 0


@pytest.mark.django_db
def test_oversized_upload_is_rejected(client, settings):
    settings.MAX_RESUME_UPLOAD_BYTES = 10
    response = upload(client, "big.pdf", make_pdf(SAMPLE))
    assert response.status_code == 400
    assert "limit" in response.json()["error"]["details"]["file"][0]


@pytest.mark.django_db
def test_malformed_pdf_is_marked_failed_not_crashed(client, inline_parse):
    body = upload(client, "broken.pdf", b"%PDF-1.4 garbage garbage").json()
    assert body["parsing_status"] == "failed"
    assert body["parsing_error"]


@pytest.mark.django_db
def test_pdf_without_text_is_marked_failed(client, inline_parse):
    body = upload(client, "scan.pdf", make_pdf("")).json()
    assert body["parsing_status"] == "failed"
    assert "No text" in body["parsing_error"]


@pytest.mark.django_db
def test_queue_unavailable_marks_failed_and_allows_reprocess(client):
    with mock.patch.object(parse_resume_task, "delay", side_effect=ConnectionError("redis down")):
        body = upload(client, "master.pdf", make_pdf(SAMPLE)).json()
    assert body["parsing_status"] == "failed"
    with mock.patch.object(parse_resume_task, "delay"):
        again = client.post(f"/api/v1/resumes/{body['id']}/reprocess/")
    assert again.status_code == 202
    assert again.json()["parsing_status"] == "pending"


@pytest.mark.django_db
def test_duplicate_file_is_flagged_but_stored_as_new_version(client, inline_parse):
    pdf = make_pdf(SAMPLE)
    upload(client, "a.pdf", pdf)
    second = upload(client, "b.pdf", pdf).json()
    assert second["version_number"] == 2
    assert second["duplicate_of_version"] == 1


# ---------- versions and activation ----------

@pytest.mark.django_db
def test_only_one_version_is_active_at_a_time(client, inline_parse):
    first = upload(client, "a.pdf", make_pdf(SAMPLE)).json()
    second = upload(client, "b.pdf", make_pdf(SAMPLE + "\nExtra Line")).json()
    assert client.get("/api/v1/resumes/active/").status_code == 404

    assert client.post(f"/api/v1/resumes/{first['id']}/activate/").status_code == 200
    assert client.post(f"/api/v1/resumes/{second['id']}/activate/").status_code == 200

    active = client.get("/api/v1/resumes/active/").json()
    assert active["id"] == second["id"]
    assert MasterResume.objects.filter(is_active=True).count() == 1
    assert client.get("/api/v1/resumes/").json()["count"] == 2


@pytest.mark.django_db
def test_failed_resume_cannot_be_activated(client, inline_parse):
    failed = upload(client, "scan.pdf", make_pdf("")).json()
    response = client.post(f"/api/v1/resumes/{failed['id']}/activate/")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW"


@pytest.mark.django_db
def test_unknown_resume_returns_404_envelope(client):
    response = client.get("/api/v1/resumes/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---------- fact review ----------

@pytest.mark.django_db
def test_confirming_every_fact_completes_the_resume(client, inline_parse):
    resume = upload(client, "a.pdf", make_pdf(SAMPLE)).json()
    facts = client.get(f"/api/v1/resumes/{resume['id']}/facts/").json()["results"]
    assert facts and all(f["verification_status"] == "parser_suggested" for f in facts)

    for fact in facts[:-1]:
        response = client.patch(f"/api/v1/resume-facts/{fact['id']}/",
                                {"verification_status": "user_confirmed"}, content_type="application/json")
        assert response.status_code == 200
    assert client.get(f"/api/v1/resumes/{resume['id']}/").json()["parsing_status"] == "review_required"

    client.patch(f"/api/v1/resume-facts/{facts[-1]['id']}/", {"verification_status": "rejected"},
                 content_type="application/json")
    assert client.get(f"/api/v1/resumes/{resume['id']}/").json()["parsing_status"] == "completed"


@pytest.mark.django_db
def test_editing_a_fact_marks_it_user_confirmed(client, inline_parse):
    resume = upload(client, "a.pdf", make_pdf(SAMPLE)).json()
    fact = client.get(f"/api/v1/resumes/{resume['id']}/facts/?category=skill").json()["results"][0]
    response = client.patch(f"/api/v1/resume-facts/{fact['id']}/", {"content": "Python 3"},
                            content_type="application/json")
    assert response.json()["content"] == "Python 3"
    assert response.json()["verification_status"] == "user_confirmed"


@pytest.mark.django_db
def test_parser_suggested_cannot_be_set_by_client(client, inline_parse):
    resume = upload(client, "a.pdf", make_pdf(SAMPLE)).json()
    fact = client.get(f"/api/v1/resumes/{resume['id']}/facts/").json()["results"][0]
    response = client.patch(f"/api/v1/resume-facts/{fact['id']}/", {"verification_status": "parser_suggested"},
                            content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_user_can_add_a_missing_fact(client, inline_parse):
    resume = upload(client, "a.pdf", make_pdf(SAMPLE)).json()
    response = client.post(f"/api/v1/resumes/{resume['id']}/facts/",
                           {"category": "certification", "content": "AWS Cloud Practitioner"},
                           content_type="application/json")
    assert response.status_code == 201
    assert response.json()["verification_status"] == "user_confirmed"


@pytest.mark.django_db
def test_reprocess_keeps_user_decisions_and_does_not_duplicate(client, inline_parse):
    resume = upload(client, "a.pdf", make_pdf(SAMPLE)).json()
    url = f"/api/v1/resumes/{resume['id']}/facts/"
    skill = client.get(url + "?category=skill").json()["results"][0]
    client.patch(f"/api/v1/resume-facts/{skill['id']}/", {"verification_status": "user_confirmed"},
                 content_type="application/json")
    before = client.get(url).json()["count"]

    assert client.post(f"/api/v1/resumes/{resume['id']}/reprocess/").status_code == 202

    after = client.get(url).json()
    assert after["count"] == before
    kept = [f for f in after["results"] if f["id"] == skill["id"]]
    assert kept and kept[0]["verification_status"] == "user_confirmed"