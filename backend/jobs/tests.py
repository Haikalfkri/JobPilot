from datetime import timedelta
from unittest import mock

import httpx
import pytest
from django.test import Client
from django.utils import timezone

from . import discovery, services
from .discovery import run_discovery
from .ingestion import ingest_listing
from .models import DiscoveryRun, Job, JobSource, JobSourceListing, JobStatus
from .normalization import (
    canonical_url, classify_geo, detect_level, detect_work_arrangement, html_to_text, normalize,
    normalize_title,
)
from .sources.arbeitnow import ArbeitnowAdapter
from .sources.base import ListingError, ParsedListing, SourceError
from .sources.jobicy import JobicyAdapter
from .tasks import discover_jobs_task, verify_job_task
from .verification import verify_job

LONG = "You will design, build and maintain backend services and APIs for our customers. " * 4


def jobicy_job(id_, title="Senior Python Developer", geo="Anywhere", level="Senior", extra=""):
    return {
        "id": id_, "url": f"https://jobicy.com/jobs/{id_}-{title.lower().replace(' ', '-')}?utm_source=feed",
        "jobTitle": title, "companyName": "Acme", "jobIndustry": ["Engineering"], "jobType": ["full-time"],
        "jobGeo": geo, "jobLevel": level, "jobExcerpt": "Short",
        "jobDescription": f"<p>Build <b>APIs</b> with Django.</p><ul><li>Python</li></ul><p>{LONG}{extra}</p>",
        "pubDate": (timezone.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S"),
        "annualSalaryMin": "85000", "annualSalaryMax": "95000", "salaryCurrency": "USD",
    }


JOBICY = {"jobCount": 3, "jobs": [
    jobicy_job(101),
    jobicy_job(102, "Backend Engineer", geo="USA", level="Any"),
    jobicy_job(103, "Junior Django Developer", geo="APAC", level="Junior"),
]}


def arbeitnow_job(slug, title="Python Developer (m/f/d)", remote=False, location="Berlin, Germany", tags=("Python",)):
    return {
        "slug": slug, "company_name": "Beta GmbH", "title": title, "description": f"<p>{LONG}</p>",
        "remote": remote, "url": f"https://www.arbeitnow.com/jobs/companies/beta/{slug}",
        "tags": list(tags), "job_types": ["Vollzeit"], "location": location, "created_at": 1762500000,
    }


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def json_handler(payload, status=200):
    return lambda request: httpx.Response(status, json=payload)


@pytest.fixture(autouse=True)
def no_delay(settings):
    settings.DISCOVERY_REQUEST_DELAY_SECONDS = 0


@pytest.fixture
def sources(db):
    services.sync_sources()
    return {s.key: s for s in JobSource.objects.all()}


def add_job(sources, raw=None, adapter=None, source="jobicy"):
    adapter = adapter or JobicyAdapter()
    ingest_listing(sources[source], adapter.parse(raw or jobicy_job(1)))
    return Job.objects.latest("created_at")


# ---------- normalization ----------

def test_html_to_text_strips_markup_and_keeps_structure():
    text = html_to_text("<p>Hello &amp; welcome</p><ul><li>Python</li><li>SQL</li></ul><script>x()</script>")
    assert text == "Hello & welcome\n\n\u2022 Python\n\u2022 SQL"
    assert "<" not in html_to_text("<img src=x onerror=alert(1)>Hi")


def test_title_normalization_removes_gender_markers():
    assert normalize_title("Python Developer (m/f/d) ") == "python developer"
    assert normalize_title("Backend Engineer (f/m/x)") == "backend engineer"


@pytest.mark.parametrize("geo,expected,countries", [
    ("Anywhere", "worldwide", None),
    ("USA", "country_specific", ["US"]),
    ("USA, Canada", "country_specific", ["CA", "US"]),
    ("Europe", "region_specific", ["EUROPE"]),
    ("APAC", "apac", None),
    ("Narnia", "unknown", None),
    (None, "unknown", None),
])
def test_remote_eligibility_is_never_guessed(geo, expected, countries):
    assert classify_geo(geo) == (expected, countries)


@pytest.mark.parametrize("remote,location,title,expected", [
    (True, None, "Dev", "remote"),
    (False, "Berlin", "Dev", "unknown"),  # "not flagged remote" is not "on-site"
    (False, "Berlin (Hybrid)", "Dev", "hybrid"),
    (None, "Remote - EU", "Dev", "remote"),
    (False, "On-site Batam", "Dev", "onsite"),
])
def test_work_arrangement(remote, location, title, expected):
    assert detect_work_arrangement(remote, location, title) == expected


@pytest.mark.parametrize("level,title,expected", [
    ("Senior", "Dev", "senior"), ("Any", "Junior Dev", "junior"),
    (None, "Associate Software Engineer", "associate"), (None, "Graduate Engineer", "graduate"),
    (None, "Software Engineer", "unknown"), ("Midweight", "Dev", "mid"),
])
def test_experience_level(level, title, expected):
    assert detect_level(level, title) == expected


def test_canonical_url_strips_tracking_and_rejects_bad_schemes():
    assert canonical_url("HTTPS://Jobicy.com/jobs/1/?utm_source=a&b=2#top") == "https://jobicy.com/jobs/1?b=2"
    with pytest.raises(ListingError):
        canonical_url("javascript:alert(1)")


def test_unflagged_arbeitnow_job_keeps_unknowns_instead_of_guessing():
    norm = normalize(ArbeitnowAdapter().parse(arbeitnow_job("a1")))
    fields = norm.job_fields
    assert fields["work_arrangement"] == "unknown" and fields["remote_eligibility"] == "unknown"
    assert fields["country_code"] == "DE" and fields["employment_type"] == "full_time"
    assert fields["normalized_title"] == "python developer"


# ---------- adapters (no network: httpx.MockTransport) ----------

def test_jobicy_search_uses_keyword_tags_and_dedupes_across_queries():
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=JOBICY)

    adapter = JobicyAdapter(client=client_for(handler))
    jobs = list(adapter.search({"keywords": ["python", "django", "go"]}))  # "go" is too short for the API
    assert [p["tag"] for p in seen] == ["python", "django"]
    assert all(p["count"] == "50" for p in seen)
    assert len(jobs) == 3


def test_jobicy_parse_maps_fields_and_assumes_utc():
    parsed = JobicyAdapter().parse(JOBICY["jobs"][0])
    assert parsed.external_id == "101" and parsed.remote is True
    assert parsed.geo_restriction == "Anywhere" and parsed.level_text == "Senior"
    assert str(parsed.salary_min) == "85000" and parsed.salary_currency == "USD"
    assert parsed.published_at.utcoffset() == timedelta(0)


def test_arbeitnow_filters_keywords_client_side_and_follows_pages():
    pages = {
        "1": {"data": [arbeitnow_job("a1"), arbeitnow_job("a2", "Java Developer", tags=("Java",))],
              "links": {"next": "x"}},
        "2": {"data": [], "links": {"next": None}},
    }
    requested = []

    def handler(request):
        requested.append(request.url.params["page"])
        return httpx.Response(200, json=pages[request.url.params["page"]])

    adapter = ArbeitnowAdapter(client=client_for(handler))
    found = list(adapter.search({"keywords": ["python"]}))
    assert [j["slug"] for j in found] == ["a1"]
    assert requested == ["1", "2"]
    assert len(list(ArbeitnowAdapter(client=client_for(handler)).search({"keywords": []}))) == 2


@pytest.mark.parametrize("handler,code", [
    (lambda r: httpx.Response(429), "RATE_LIMITED"),
    (lambda r: httpx.Response(500), "HTTP_500"),
    (lambda r: httpx.Response(200, text="<html>not json"), "BAD_RESPONSE"),
    (lambda r: (_ for _ in ()).throw(httpx.ConnectError("down")), "NETWORK_ERROR"),
])
def test_adapter_errors_are_typed(handler, code):
    with pytest.raises(SourceError) as error:
        list(JobicyAdapter(client=client_for(handler)).search({"keywords": []}))
    assert error.value.code == code


# ---------- ingestion and deduplication ----------

@pytest.mark.django_db
def test_second_identical_ingest_is_ignored_and_changed_content_is_an_update(sources):
    adapter = JobicyAdapter()
    raw = jobicy_job(1)
    assert ingest_listing(sources["jobicy"], adapter.parse(raw)) == "created"
    assert ingest_listing(sources["jobicy"], adapter.parse(raw)) == "ignored"
    assert ingest_listing(sources["jobicy"], adapter.parse(jobicy_job(1, extra=" New benefit."))) == "updated"
    assert Job.objects.count() == 1 and JobSourceListing.objects.count() == 1
    job = Job.objects.get()
    assert job.status == "active" and job.last_verified_at is None  # not verified, only listed
    assert job.remote_eligibility == "worldwide" and job.work_arrangement == "remote"


@pytest.mark.django_db
def test_same_job_on_two_sources_is_one_job_with_two_listings(sources):
    first = jobicy_job(1)
    ingest_listing(sources["jobicy"], JobicyAdapter().parse(first))
    syndicated = ParsedListing(external_id="x9", url="https://www.arbeitnow.com/jobs/x9", title=first["jobTitle"],
                               company_name="ACME", description=first["jobDescription"], remote=True)
    assert ingest_listing(sources["arbeitnow"], syndicated) == "updated"
    job = Job.objects.get()
    assert job.listings.count() == 2
    assert {l.source.key for l in job.listings.select_related("source")} == {"jobicy", "arbeitnow"}


@pytest.mark.django_db
def test_same_title_but_different_role_is_not_merged(sources):
    ingest_listing(sources["jobicy"], JobicyAdapter().parse(jobicy_job(1)))
    other = jobicy_job(2)
    other["jobDescription"] = "<p>" + "Completely different duties around sales forecasting spreadsheets. " * 4 + "</p>"
    ingest_listing(sources["jobicy"], JobicyAdapter().parse(other))
    assert Job.objects.count() == 2


@pytest.mark.django_db
def test_listings_without_enough_text_are_never_merged_by_content(sources):
    for ext in ("1", "2"):
        raw = jobicy_job(ext)
        raw["jobDescription"] = raw["jobExcerpt"] = "Short"
        ingest_listing(sources["jobicy"], JobicyAdapter().parse(raw))
    assert Job.objects.count() == 2


@pytest.mark.django_db
def test_same_url_with_different_tracking_params_is_the_same_job(sources):
    a = ParsedListing(None, "https://jobicy.com/jobs/5-x?utm_source=a", "Dev", "Acme", "Short")
    b = ParsedListing(None, "https://jobicy.com/jobs/5-x?utm_source=b", "Dev", "Acme", "Short")
    assert ingest_listing(sources["jobicy"], a) == "created"
    assert ingest_listing(sources["jobicy"], b) == "ignored"
    assert Job.objects.count() == 1


@pytest.mark.django_db
def test_unusable_listing_creates_nothing(sources):
    bad = ParsedListing("1", "javascript:alert(1)", "Dev", "Acme", "x")
    with pytest.raises(ListingError):
        ingest_listing(sources["jobicy"], bad)
    assert Job.objects.count() == 0


# ---------- discovery: sources fail independently ----------

class FakeAdapter:
    def __init__(self, items=(), error=None, bad_parse=()):
        self.items, self.error, self.bad_parse = list(items), error, set(bad_parse)
        self._real = JobicyAdapter()

    def search(self, criteria):
        for item in self.items:
            yield item
        if self.error:
            raise self.error

    def parse(self, raw):
        if raw["id"] in self.bad_parse:
            raise ListingError("bad listing")
        return self._real.parse(raw)


def make_run(keys):
    return DiscoveryRun.objects.create(trigger_type="manual", criteria={"source_keys": keys, "keywords": []})


def patch_adapters(monkeypatch, mapping):
    monkeypatch.setattr(discovery.registry, "get_adapter", lambda key, **kw: mapping[key])


@pytest.mark.django_db
def test_one_failing_source_does_not_stop_the_other(sources, monkeypatch):
    patch_adapters(monkeypatch, {
        "jobicy": FakeAdapter(error=SourceError("RATE_LIMITED", "slow down")),
        "arbeitnow": FakeAdapter(items=[jobicy_job(1), jobicy_job(2, "Backend Engineer")]),
    })
    run = make_run(["jobicy", "arbeitnow"])
    run_discovery(run.id)
    run.refresh_from_db()
    results = {sr.source.key: sr for sr in run.source_runs.select_related("source")}
    assert run.status == "partial"
    assert results["jobicy"].status == "failed" and results["jobicy"].error_code == "RATE_LIMITED"
    assert results["arbeitnow"].status == "completed" and results["arbeitnow"].created_count == 2
    assert Job.objects.count() == 2
    assert run.summary["created"] == 2 and run.finished_at is not None


@pytest.mark.django_db
def test_every_source_failing_marks_the_run_failed(sources, monkeypatch):
    err = SourceError("NETWORK_ERROR", "down")
    patch_adapters(monkeypatch, {"jobicy": FakeAdapter(error=err), "arbeitnow": FakeAdapter(error=err)})
    run = make_run(["jobicy", "arbeitnow"])
    run_discovery(run.id)
    run.refresh_from_db()
    assert run.status == "failed"


@pytest.mark.django_db
def test_failure_midway_keeps_what_was_already_saved(sources, monkeypatch):
    patch_adapters(monkeypatch, {"jobicy": FakeAdapter(items=[jobicy_job(1)], error=SourceError("HTTP_500", "x"))})
    run = make_run(["jobicy"])
    run_discovery(run.id)
    source_run = run.source_runs.get()
    assert source_run.status == "partial" and source_run.fetched_count == 1
    assert Job.objects.count() == 1


@pytest.mark.django_db
def test_a_bad_listing_is_skipped_not_fatal(sources, monkeypatch):
    patch_adapters(monkeypatch, {"jobicy": FakeAdapter(items=[jobicy_job(1), jobicy_job(2, "Other Role")],
                                                       bad_parse=[1])})
    run = make_run(["jobicy"])
    run_discovery(run.id)
    source_run = run.source_runs.get()
    assert source_run.status == "partial" and source_run.error_code == "INVALID_LISTINGS"
    assert source_run.created_count == 1 and source_run.ignored_count == 1


# ---------- API ----------

@pytest.fixture
def client():
    return Client()


@pytest.fixture
def inline_discovery(monkeypatch):
    monkeypatch.setattr(discovery.registry, "get_adapter", lambda key, **kw: FakeAdapter(items=JOBICY["jobs"]))
    with mock.patch.object(discover_jobs_task, "delay", side_effect=lambda rid: run_discovery(rid)) as patched:
        yield patched


def post_json(client, url, body):
    return client.post(url, body, content_type="application/json")


@pytest.mark.django_db
def test_discover_runs_and_reports_counts(client, inline_discovery):
    response = post_json(client, "/api/v1/jobs/discover/", {"source_keys": ["jobicy"], "keywords": ["python"]})
    assert response.status_code == 202
    run = client.get(f"/api/v1/jobs/discovery-runs/{response.json()['discovery_run_id']}/").json()
    assert run["status"] == "completed" and run["criteria"]["keywords"] == ["python"]
    assert run["summary"]["created"] == 3
    assert run["source_runs"][0]["source_key"] == "jobicy"
    assert client.get("/api/v1/jobs/discovery-runs/").json()["count"] == 1


@pytest.mark.django_db
def test_discover_rejects_unknown_source_and_concurrent_runs(client, inline_discovery):
    bad = post_json(client, "/api/v1/jobs/discover/", {"source_keys": ["linkedin"]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "VALIDATION_ERROR"

    DiscoveryRun.objects.create(trigger_type="manual", status="running", criteria={})
    busy = post_json(client, "/api/v1/jobs/discover/", {})
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "CONFLICT"


@pytest.mark.django_db
def test_stale_running_run_does_not_block_new_discovery(client, inline_discovery):
    stale = DiscoveryRun.objects.create(trigger_type="manual", status="running", criteria={})
    DiscoveryRun.objects.filter(pk=stale.pk).update(started_at=timezone.now() - timedelta(hours=2))
    assert post_json(client, "/api/v1/jobs/discover/", {}).status_code == 202


@pytest.mark.django_db
def test_discover_returns_503_when_queue_is_down(client):
    with mock.patch.object(discover_jobs_task, "delay", side_effect=ConnectionError("redis")):
        response = post_json(client, "/api/v1/jobs/discover/", {})
    assert response.status_code == 503
    assert DiscoveryRun.objects.get().status == "failed"


@pytest.mark.django_db
def test_disabled_sources_are_not_discovered(client, inline_discovery):
    listing = client.get("/api/v1/job-sources/").json()
    source = next(s for s in listing if s["key"] == "arbeitnow")
    patched = client.patch(f"/api/v1/job-sources/{source['id']}/", {"is_enabled": False},
                           content_type="application/json")
    assert patched.status_code == 200 and patched.json()["is_enabled"] is False
    assert post_json(client, "/api/v1/jobs/discover/", {"source_keys": ["arbeitnow"]}).status_code == 400
    run_id = post_json(client, "/api/v1/jobs/discover/", {}).json()["discovery_run_id"]
    assert client.get(f"/api/v1/jobs/discovery-runs/{run_id}/").json()["criteria"]["source_keys"] == ["jobicy"]


@pytest.mark.django_db
def test_job_list_filters_detail_and_source_transparency(client, sources):
    ingest_listing(sources["jobicy"], JobicyAdapter().parse(JOBICY["jobs"][0]))  # worldwide, senior
    ingest_listing(sources["jobicy"], JobicyAdapter().parse(JOBICY["jobs"][2]))  # apac, junior
    ingest_listing(sources["arbeitnow"], ArbeitnowAdapter().parse(arbeitnow_job("a1")))  # unknown

    def ids(query):
        return {j["title"] for j in client.get(f"/api/v1/jobs/?{query}").json()["results"]}

    assert client.get("/api/v1/jobs/").json()["count"] == 3
    assert ids("remote_eligibility=apac") == {"Junior Django Developer"}
    assert ids("work_arrangement=remote&experience_level=senior") == {"Senior Python Developer"}
    assert ids("q=beta") == {"Python Developer (m/f/d)"}
    assert ids("source=arbeitnow&country_code=de") == {"Python Developer (m/f/d)"}
    assert ids("published_within_days=1") == set()  # arbeitnow sample is old, jobicy ones are 2 days old
    assert len(ids("published_within_days=5")) == 2
    assert client.get("/api/v1/jobs/?work_arrangement=nonsense").status_code == 400

    job = client.get("/api/v1/jobs/?q=Senior").json()["results"][0]
    assert job["sources"][0]["original_url"].startswith("https://jobicy.com/")
    detail = client.get(f"/api/v1/jobs/{job['id']}/").json()
    assert "Build APIs with Django." in detail["description"] and "<p>" not in detail["description"]
    assert detail["listings"][0]["source_name"] == "Jobicy"
    assert client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000/").json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_verify_endpoint_queues_a_task(client, sources):
    job = add_job(sources)
    with mock.patch.object(verify_job_task, "delay") as queued:
        response = client.post(f"/api/v1/jobs/{job.id}/verify/")
    assert response.status_code == 202 and response.json()["status"] == "queued"
    queued.assert_called_once_with(str(job.id))


# ---------- verification ----------

@pytest.mark.django_db
@pytest.mark.parametrize("status_code,job_status,verified", [
    (200, "active", True), (404, "closed", True), (410, "closed", True),
    (500, "unknown", False), (403, "unknown", False), (301, "unknown", False),
])
def test_verification_only_closes_on_clear_evidence(sources, status_code, job_status, verified):
    job = add_job(sources)
    verify_job(job, client=client_for(lambda r: httpx.Response(status_code)))
    job.refresh_from_db()
    assert job.status == job_status
    assert (job.last_verified_at is not None) is verified
    assert job.listings.get().last_checked_at is not None


@pytest.mark.django_db
def test_verification_never_requests_unknown_hosts(sources):
    job = add_job(sources)
    JobSourceListing.objects.filter(job=job).update(original_url="https://evil.example/steal")
    calls = []
    verify_job(job, client=client_for(lambda r: calls.append(r) or httpx.Response(200)))
    job.refresh_from_db()
    assert calls == [] and job.status == JobStatus.UNKNOWN


@pytest.mark.django_db
def test_network_error_during_verification_is_unknown_not_closed(sources):
    job = add_job(sources)
    verify_job(job, client=client_for(lambda r: (_ for _ in ()).throw(httpx.ConnectError("down"))))
    job.refresh_from_db()
    assert job.status == "unknown"


# ---------- management command ----------

def test_inspect_source_command_prints_raw_fields_and_parsed_result(capsys):
    from django.core.management import call_command

    adapter = JobicyAdapter(client=client_for(json_handler(JOBICY)))
    with mock.patch("jobs.management.commands.inspect_source.get_adapter", return_value=adapter):
        call_command("inspect_source", "jobicy")
    output = capsys.readouterr().out
    assert "Raw fields:" in output and "jobTitle" in output
    assert '"remote_eligibility": "worldwide"' in output


@pytest.mark.django_db
def test_discovery_queues_a_match_refresh_only_when_something_changed(sources, monkeypatch, task_bus):
    patch_adapters(monkeypatch, {"jobicy": FakeAdapter(items=[jobicy_job(1)])})
    run_discovery(make_run(["jobicy"]).id)
    assert [name for name, _, _ in task_bus] == ["matching.tasks.refresh_matches_task"]

    task_bus.clear()
    run_discovery(make_run(["jobicy"]).id)  # the same listing again: nothing new, nothing to rescore
    assert task_bus == []