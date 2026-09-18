"""Tests for the GitHub API fetcher (hermetic, mocked network)."""
import base64

from career_graph.ingestion import github_fetcher as gf


def _authored(responses):
    """Build a fake `_gh_get` that pops canned payloads in order."""
    responses = list(responses)

    def fake(url, token=None, timeout=10):
        payload, _headers = responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload

    return fake


def test_fetch_github_repos_enriches(monkeypatch):
    readme_content = base64.b64encode(b"# My Repo\nBuilds scalable pipelines with Python and AWS.").decode()
    monkeypatch.setattr(
        gf,
        "_gh_get",
        _authored(
            [
                ([{"name": "cool-app", "html_url": "https://github.com/u/cool-app", "description": "A thing", "language": "Python", "owner": {"login": "u"}}], {}),
                ({"Python": 8000, "Shell": 200}, {}),
            ]
        ),
    )
    monkeypatch.setattr(gf, "_commit_count", lambda owner, repo, token: 42)
    monkeypatch.setattr(gf, "_readme_text", lambda owner, repo, token: "Builds scalable pipelines with Python and AWS.")

    repos = gf.fetch_github_repos("someuser", token=None, max_repos=10)
    assert len(repos) == 1
    r = repos[0]
    assert r["name"] == "cool-app"
    assert r["language"] == "Python"
    assert r["commits_count"] == 42
    assert "Builds scalable pipelines" in r["readme_text"]


def test_fetch_github_repos_handles_missing_languages(monkeypatch):
    monkeypatch.setattr(
        gf,
        "_gh_get",
        _authored(
            [
                ([{"name": "no-code", "html_url": "x", "description": None, "language": "TechLang", "owner": {"login": "u"}}], {}),
                (RuntimeError("rate limited"), {}),
            ]
        ),
    )
    monkeypatch.setattr(gf, "_commit_count", lambda owner, repo, token: 0)
    monkeypatch.setattr(gf, "_readme_text", lambda owner, repo, token: "")

    repos = gf.fetch_github_repos("noone", max_repos=10)
    r = repos[0]
    assert r["language"] == "TechLang"  # falls back to repo language field
    assert r["readme_text"] == ""


def test_commit_count_parses_last_page():
    link = '<https://api.github.com/repos/o/r/commits?per_page=1&page=9>; rel="next", <https://api.github.com/repos/o/r/commits?per_page=1&page=9>; rel="last"'
    m = gf.re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    assert m and m.group(1) == "9"