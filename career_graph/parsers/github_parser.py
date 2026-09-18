from typing import Dict, Any, List, Set


class GithubParser:
    """Parses GitHub repo dicts into projects and inferred skills.

    Improvements: normalize language names, deduplicate skills, attach source metadata.
    """

    def _normalize_language(self, lang: str) -> str:
        if not lang:
            return ""
        return lang.split()[0].capitalize()

    def parse(self, raw: List[Dict[str, Any]]) -> Dict[str, Any]:
        projects = []
        skills: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for r in raw:
            language = self._normalize_language(r.get("language"))
            projects.append({
                "name": r.get("name"),
                "description": r.get("description"),
                "url": r.get("html_url"),
                "commit_count": r.get("commits_count", 0),
                "source": "github",
                "skills": [language] if language else [],
            })
            if language and language.lower() not in seen:
                skills.append({"canonical_name": language, "confidence": 0.7})
                seen.add(language.lower())

        return {"name": None, "email": None, "skills": skills, "projects": projects}