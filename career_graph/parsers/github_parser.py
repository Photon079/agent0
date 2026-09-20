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
        from .simple_resume_parser import SimpleResumeParser
        import re

        projects = []
        skills: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        for r in raw:
            language = self._normalize_language(r.get("language"))
            proj_skills = []
            if language:
                proj_skills.append(language)
                if language.lower() not in seen:
                    skills.append({"canonical_name": language, "confidence": 0.7})
                    seen.add(language.lower())
            
            # Extract frameworks and software from description and readme
            text_to_search = f"{r.get('name', '')} {r.get('description', '')} {r.get('readme_text', '')}".lower()
            
            for canonical, variants in SimpleResumeParser.SKILL_KEYWORDS.items():
                for variant in variants:
                    # Look for exact word matches to prevent false positives (e.g. 'go' matching 'good')
                    pattern = r'\b' + re.escape(variant) + r'\b'
                    if re.search(pattern, text_to_search):
                        if canonical.capitalize() not in proj_skills and canonical not in [s.lower() for s in proj_skills]:
                            proj_skills.append(canonical.capitalize())
                        if canonical.lower() not in seen:
                            skills.append({"canonical_name": canonical.capitalize(), "confidence": 0.6})
                            seen.add(canonical.lower())
                        break # Found one variant, no need to check others for this canonical skill

            projects.append({
                "name": r.get("name"),
                "description": r.get("description"),
                "url": r.get("html_url"),
                "commit_count": r.get("commits_count", 0),
                "source": "github",
                "skills": proj_skills,
            })

        return {"name": None, "email": None, "skills": skills, "projects": projects}