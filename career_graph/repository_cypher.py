from .falkor import query


def match_jobs_by_skill_overlap(candidate_id: str, limit: int = 10):
    q = """
    MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill)<-[r:REQUIRES]-(j:JobPosting)
    WHERE c.id = $candidate_id OR c.id = 'cand:' + $candidate_id
    RETURN j.id AS job_id, j.title AS title, j.company AS company, j.url AS url,
           count(s) AS overlap_score, collect(s.canonical_name) AS matched_skills
    ORDER BY overlap_score DESC
    LIMIT $limit
    """
    return query(q, {"candidate_id": str(candidate_id), "limit": limit})


def gap_detection(candidate_id: str, job_id: str):
    # FalkorDB does not support `WHERE NOT EXISTS { MATCH ... }`, so use
    # OPTIONAL MATCH + `WHERE c IS NULL` to find required-but-missing skills.
    q = """
    MATCH (j:JobPosting)-[r:REQUIRES]->(s:Skill)
    WHERE j.id = $job_id OR j.id = 'job:' + $job_id
    OPTIONAL MATCH (c:Candidate)-[:HAS_SKILL]->(s)
    WHERE c.id = $candidate_id OR c.id = 'cand:' + $candidate_id
    WITH s, r, c
    WHERE c IS NULL
    RETURN s.canonical_name AS missing_skill, r.importance AS importance, s.category AS category
    """
    return query(q, {"candidate_id": str(candidate_id), "job_id": str(job_id)})


def evidence_for_skill_for_candidate(candidate_id: str, matched_skills: list):
    """Retrieve grounded evidence (projects + corporate experiences) for candidate skills.

    Traverses both Project nodes (GitHub repos) and Experience nodes (work history)
    to prevent evidence blind spots for skills acquired in corporate roles.
    """
    if not matched_skills:
        return query(
            "MATCH (c:Candidate) WHERE c.id = $candidate_id OR c.id = 'cand:' + $candidate_id RETURN 1 LIMIT 0",
            {"candidate_id": str(candidate_id)},
        )

    q = """
    UNWIND $skills AS skill_name
    MATCH (c:Candidate)
    WHERE c.id = $candidate_id OR c.id = 'cand:' + $candidate_id
    OPTIONAL MATCH (c)-[:BUILT]->(p:Project)-[:USES]->(s1:Skill {canonical_name: skill_name})
    OPTIONAL MATCH (c)-[:HAD]->(e:Experience)
    WHERE e.description CONTAINS skill_name
    RETURN skill_name AS skill,
           collect(DISTINCT {type: 'project', name: p.name, description: p.description, commits: p.commit_count, url: p.url}) AS project_evidence,
           collect(DISTINCT {type: 'experience', role: e.title, company: e.company, duration: e.start_date + ' - ' + e.end_date}) AS experience_evidence
    """
    return query(q, {"candidate_id": str(candidate_id), "skills": matched_skills})


def evidence_for_skill(skill_identifier: str):
    """Return projects, candidates, and experiences that support this skill in FalkorDB."""
    q = """
    MATCH (s:Skill)
    WHERE toLower(s.canonical_name) = toLower($skill) OR s.canonical_name = $skill
    OPTIONAL MATCH (p:Project)-[u:USES]->(s)
    OPTIONAL MATCH (c:Candidate)-[h:HAS_SKILL]->(s)
    OPTIONAL MATCH (c)-[:HAD]->(e:Experience)
    WHERE e.description CONTAINS s.canonical_name
    RETURN s.canonical_name AS skill,
           collect(DISTINCT {id: p.name, name: p.name, evidence: p.description}) AS projects,
           collect(DISTINCT {id: c.id, name: c.name, evidence: h.evidence}) AS candidates,
           collect(DISTINCT {type: 'experience', role: e.title, company: e.company, duration: e.start_date + ' - ' + e.end_date}) AS experiences
    """
    res = query(q, {"skill": str(skill_identifier)})
    if not res.result_set:
        return {"projects": [], "candidates": [], "experiences": []}
    row = res.result_set[0]
    projects = [p for p in row[1] if p.get("name") is not None]
    candidates = [c for c in row[2] if c.get("id") is not None]
    experiences = [e for e in row[3] if e.get("role") is not None or e.get("company") is not None]
    return {
        "skill": row[0],
        "projects": projects,
        "candidates": candidates,
        "experiences": experiences,
    }