from career_graph.parsers.simple_resume_parser import SimpleResumeParser
from career_graph.parsers.github_parser import GithubParser
from career_graph.parsers.job_parser import JobParser


def test_simple_resume_parser():
    text = """Eve Example\neve@example.com\nExperienced in Python and SQL. See https://github.com/eve/demo"""
    p = SimpleResumeParser()
    parsed = p.parse(text)
    assert parsed["email"] == "eve@example.com"
    assert any(s["canonical_name"].lower() == "python" for s in parsed["skills"]) 


def test_github_parser():
    repos = [{"name": "demo", "html_url": "https://github.com/x/demo", "language": "Python"}]
    p = GithubParser()
    parsed = p.parse(repos)
    assert parsed["projects"]
    assert any(s["canonical_name"].lower() == "python" for s in parsed["skills"]) 


def test_job_parser():
    text = "Senior Engineer\nAcme\nWe use Python and Docker"
    p = JobParser()
    parsed = p.parse(text)
    assert parsed["title"] == "Senior Engineer"
    assert any(s["canonical_name"].lower() == "python" for s in parsed["skills"]) 
