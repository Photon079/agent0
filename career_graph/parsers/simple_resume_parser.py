import re
from typing import Dict, Any, List, Set
from .interfaces import Parser


class SimpleResumeParser:
    """A heuristic text resume parser for fixtures and local testing.

    Improvements over the previous version:
    - Better name detection (first line with two capitalized words)
    - Email extraction
    - Skill extraction with synonyms and deduplication
    - Project URL detection (github/http) and basic normalization
    - Returns evidence for each skill (text snippet)
    """

    SKILL_KEYWORDS = {
        "python": ["python", "python3", "pytest"],
        "javascript": ["javascript", "js", "es6"],
        "typescript": ["typescript", "ts"],
        "java": ["java", "spring", "spring boot", "maven", "gradle"],
        "go": ["golang", "go lang", "go"],
        "c++": ["c++", "cpp"],
        "c#": ["c#", "csharp", ".net", "dotnet"],
        "rust": ["rust", "rustlang"],
        "ruby": ["ruby", "ruby on rails", "rails"],
        "php": ["php", "laravel", "symfony"],
        "react": ["react", "reactjs", "react.js"],
        "nextjs": ["nextjs", "next.js"],
        "vue": ["vue", "vuejs", "vue.js", "nuxtjs"],
        "angular": ["angular", "angularjs"],
        "svelte": ["svelte", "sveltekit"],
        "nodejs": ["node.js", "nodejs", "node", "express"],
        "fastapi": ["fastapi"],
        "django": ["django"],
        "flask": ["flask"],
        "sql": ["sql", "postgres", "postgresql", "mysql", "mariadb"],
        "nosql": ["mongodb", "mongo", "cassandra", "dynamodb", "couchbase"],
        "redis": ["redis", "memcached"],
        "elasticsearch": ["elasticsearch", "solr"],
        "aws": ["aws", "amazon web services", "s3", "ec2", "lambda"],
        "gcp": ["gcp", "google cloud", "google cloud platform"],
        "azure": ["azure", "microsoft azure"],
        "docker": ["docker", "docker-compose", "containers"],
        "kubernetes": ["kubernetes", "k8s", "helm"],
        "terraform": ["terraform", "infrastructure as code", "iac"],
        "git": ["git", "github", "gitlab", "bitbucket"],
        "ci/cd": ["ci/cd", "ci cd", "github actions", "jenkins", "circleci", "travis"],
        "graphql": ["graphql", "apollo"],
        "kafka": ["kafka", "apache kafka", "rabbitmq", "pubsub"],
        "machine learning": ["machine learning", "ml", "tensorflow", "pytorch", "scikit-learn", "keras", "deep learning", "ai", "artificial intelligence"],
        "linux": ["linux", "ubuntu", "bash", "shell", "unix"],
    }

    URL_RE = re.compile(r"https?://[^\s,]+")
    EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")

    def _detect_name(self, lines: List[str]) -> str:
        for l in lines[:5]:
            parts = l.split()
            if len(parts) >= 2 and all(p[0].isupper() for p in parts[:2]):
                return l
        return lines[0] if lines else "Unknown"

    def parse(self, raw: str) -> Dict[str, Any]:
        lines = [l.strip() for l in raw.splitlines() if l.strip()]

        name = self._detect_name(lines)

        email_match = self.EMAIL_RE.search(raw)
        email = email_match.group(0) if email_match else None

        text_lower = raw.lower()
        found: Set[str] = set()
        skills: List[Dict[str, Any]] = []
        for canonical, variants in self.SKILL_KEYWORDS.items():
            for v in variants:
                idx = text_lower.find(v)
                if idx != -1 and canonical not in found:
                    snippet = raw[max(0, idx - 40) : idx + 40]
                    skills.append({"canonical_name": canonical.capitalize(), "confidence": 0.85, "evidence": {"snippet": snippet}})
                    found.add(canonical)
                    break

        # project extraction: find URLs and normalize names
        projects: List[Dict[str, Any]] = []
        for m in self.URL_RE.finditer(raw):
            url = m.group(0).rstrip(".,")
            proj_name = url.split("/")[-1] or url
            projects.append({"name": proj_name, "url": url, "description": "Imported from resume"})

        return {"name": name, "email": email, "skills": skills, "projects": projects}