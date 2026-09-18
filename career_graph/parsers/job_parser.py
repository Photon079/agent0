import re
from typing import Dict, Any, List


class JobParser:
    """Improved job posting parser using simple heuristics.

    - Extracts title/company from first lines
    - Extracts skill list from bullet sections or via keywords
    - Returns skills with an importance score
    """

    SKILL_KEYWORDS = ["python", "sql", "java", "javascript", "react", "aws", "docker", "kubernetes", "typescript", "fastapi", "postgres"]
    BULLET_RE = re.compile(r"^[-*\u2022]\s*(.+)$", re.MULTILINE)

    def parse(self, raw: str) -> Dict[str, Any]:
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        title = lines[0] if lines else "Job"
        company = lines[1] if len(lines) > 1 else None

        text_lower = raw.lower()
        skills: List[Dict[str, Any]] = []

        # try to parse bullets for explicit requirements
        bullets = [m.group(1).strip() for m in self.BULLET_RE.finditer(raw)]
        if bullets:
            for b in bullets:
                for kw in self.SKILL_KEYWORDS:
                    if kw in b.lower():
                        skills.append({"canonical_name": kw.capitalize(), "importance": 1.0})

        # fallback: keyword search
        if not skills:
            for kw in self.SKILL_KEYWORDS:
                if kw in text_lower:
                    skills.append({"canonical_name": kw.capitalize(), "importance": 0.9})

        # dedupe by canonical_name
        seen = set()
        deduped = []
        for s in skills:
            name = s["canonical_name"]
            if name.lower() not in seen:
                deduped.append(s)
                seen.add(name.lower())

        return {"title": title, "company": company, "description": raw, "skills": deduped}