"""Tests for the job scraper sources, HTML stripping, and normalization."""
import json

import pytest

from career_graph.scraper import sources


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeUrlopen:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, request, timeout=10):
        self.calls.append(getattr(request, "full_url", request))
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return FakeResp(payload)


def test_strip_html():
    raw = "<h1>Hello</h1><p>Python &amp; AWS</p><br><br>Docker<br><li>One</li>"
    out = sources._strip_html(raw)
    assert "Hello" in out
    assert "&" in out
    assert "<" not in out
    assert "One" in out


def test_greenhouse_normalized(monkeypatch):
    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Backend Engineer",
                "company_name": "Stripe",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/123",
                "content": "<p>Python AWS</p>",
                "location": {"name": "Remote"},
            }
        ]
    }
    monkeypatch.setattr(sources, "_http_get_json", lambda url, timeout=10: payload)
    jobs = sources.fetch_greenhouse("stripe", limit=5)
    assert len(jobs) == 1
    j = jobs[0]
    assert j["external_id"] == "greenhouse:123"
    assert j["source"] == "greenhouse"
    assert j["title"] == "Backend Engineer"
    assert j["company"] == "Stripe"
    assert j["location"] == "Remote"
    assert "Python AWS" in j["description"]
    assert "<" not in j["description"]


def test_lever_normalized(monkeypatch):
    payload = [{"id": "abc", "text": "Frontend Eng", "company": "Lever", "hostedUrl": "https://jobs.lever.co/x/abc", "descriptionPlain": "React", "categories": {"location": "SF"}}]
    monkeypatch.setattr(sources, "_http_get_json", lambda url, timeout=10: payload)
    jobs = sources.fetch_lever("leverdemo", limit=5)
    assert jobs[0]["external_id"] == "lever:abc"
    assert jobs[0]["company"] == "Lever"
    assert jobs[0]["location"] == "SF"


def test_remoteok_drops_legend(monkeypatch):
    payload = [{"slug": "legend", "company": "n/a", "description": "legend row"}, {"id": "r1", "position": "DevOps", "company": "Acme", "url": "https://remoteok.com/1", "description": "<p>Kubernetes</p>", "location": "Remote"}]
    monkeypatch.setattr(sources, "_http_get_json", lambda url, timeout=10: payload)
    jobs = sources.fetch_remoteok(limit=5)
    assert len(jobs) == 1
    assert jobs[0]["external_id"] == "remoteok:r1"
    assert jobs[0]["title"] == "DevOps"


def test_arbeitnow_normalized(monkeypatch):
    payload = {"data": [{"id": "a1", "slug": "slug-1", "title": "ML Eng", "company_name": "BerlinCo", "description": "PyTorch", "location": "Berlin"}]}
    monkeypatch.setattr(sources, "_http_get_json", lambda url, timeout=10: payload)
    jobs = sources.fetch_arbeitnow(limit=5)
    j = jobs[0]
    assert j["external_id"] == "arbeitnow:a1"
    assert j["url"].endswith("/jobs/slug-1")


def test_fixtures_normalized():
    jobs = sources.fetch_fixtures()
    assert jobs
    j = jobs[0]
    assert j["source"] == "fixture"
    assert j["title"]
    assert "requirements" in j


def test_fetch_all_dedupes_and_tolerates_failures(monkeypatch):
    calls = {}

    def fake_fetch(source, limit, **kw):
        calls[source] = True
        if source == "greenhouse":
            return [{"external_id": "greenhouse:1", "source": "greenhouse", "title": "A"}]
        if source == "lever":
            return [{"external_id": "greenhouse:1", "source": "greenhouse", "title": "A"}, {"external_id": "lever:2", "source": "lever", "title": "B"}]
        raise RuntimeError("boom")

    monkeypatch.setattr(sources, "fetch_source", fake_fetch)
    jobs = sources.fetch_all(10, sources=["greenhouse", "lever", "remoteok"], **{"board_token": "x", "company": "y"})
    assert [j["external_id"] for j in jobs] == ["greenhouse:1", "lever:2"]


def test_fetch_source_requires_env_when_unset(monkeypatch):
    monkeypatch.delenv("GREENHOUSE_BOARD_TOKEN", raising=False)
    with pytest.raises(Exception):
        sources.fetch_source("greenhouse")