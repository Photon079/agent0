from .falkor import query


def match_jobs_by_skill_overlap(candidate_id: str, limit: int = 10):
    q = """
    MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(s:Skill)<-[r:REQUIRES]-(j:JobPosting)
    RETURN j.id AS job_id, j.title AS title, j.company AS company, j.url AS url,
           count(s) AS overlap_score, collect(s.canonical_name) AS matched_skills
    ORDER BY overlap_score DESC
    LIMIT $limit
    """
    return query(q, {"candidate_id": candidate_id, "limit": limit})


def gap_detection(candidate_id: str, job_id: str):
    # FalkorDB does not support `WHERE NOT EXISTS { MATCH ... }`, so use
    # OPTIONAL MATCH + `WHERE c IS NULL` to find required-but-missing skills.
    q = """
    MATCH (j:JobPosting {id: $job_id})-[r:REQUIRES]->(s:Skill)
    OPTIONAL MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(s)
    WITH s, r, c
    WHERE c IS NULL
    RETURN s.canonical_name AS missing_skill, r.importance AS importance, s.category AS category
    """
    return query(q, {"candidate_id": candidate_id, "job_id": job_id})


def evidence_for_skill_for_candidate(candidate_id: str, matched_skills: list):
    # matched_skills is a list of canonical names
    q = """
    UNWIND $skills AS skill_name
    MATCH (c:Candidate {id: $candidate_id})-[:BUILT]->(p:Project)-[:USES]->(s:Skill {canonical_name: skill_name})
    RETURN s.canonical_name AS skill, p.name AS project_name, p.description AS project_description, p.commit_count AS commit_count, p.url AS repository_url
    """
    return query(q, {"candidate_id": candidate_id, "skills": matched_skills})