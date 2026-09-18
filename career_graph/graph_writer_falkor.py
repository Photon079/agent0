from .falkor import query


def create_performance_indexes():
    # create indexes per PRD
    idxs = [
        "CREATE INDEX FOR (c:Candidate) ON (c.id);",
        "CREATE INDEX FOR (s:Skill) ON (s.canonical_name);",
        "CREATE INDEX FOR (j:JobPosting) ON (j.id);",
        "CREATE INDEX FOR (p:Project) ON (p.name);",
        "CREATE INDEX FOR (e:Experience) ON (e.id);",
    ]
    for s in idxs:
        try:
            query(s)
        except Exception:
            # ignore errors for idempotence (index exists etc.)
            pass


def write_candidate_graph(data: dict, normalizer):
    c = data["candidate"]

    # Upsert candidate
    query(
        "MERGE (c:Candidate {id: $id}) SET c.name = $name, c.resume_url = $url",
        {"id": c["id"], "name": c.get("name"), "url": c.get("resume_url")},
    )

    # Upsert skills and HAS_SKILL edges
    for item in data.get("skills", []):
        canonical = normalizer.normalize(item["name"])
        query(
            """
            MERGE (s:Skill {canonical_name: $canonical})
            WITH s
            MATCH (c:Candidate {id: $cid})
            MERGE (c)-[r:HAS_SKILL]->(s)
            SET r.confidence = $conf, r.evidence = $evidence
            """,
            {"canonical": canonical, "cid": c["id"], "conf": item.get("confidence", 1.0), "evidence": item.get("evidence", "")},
        )

    # Upsert projects and edges
    for proj in data.get("projects", []):
        query(
            """
            MERGE (p:Project {name: $name})
            SET p.description = $desc, p.url = $url, p.commit_count = $commits, p.source = $source
            WITH p
            MATCH (c:Candidate {id: $cid})
            MERGE (c)-[:BUILT]->(p)
            """,
            {
                "name": proj["name"],
                "desc": proj.get("description", ""),
                "url": proj.get("url", ""),
                "commits": proj.get("commit_count", 0),
                "source": proj.get("source", "github"),
                "cid": c["id"],
            },
        )

        for skill_str in proj.get("skills_used", []):
            canonical = normalizer.normalize(skill_str)
            query(
                """
                MATCH (p:Project {name: $pname})
                MERGE (s:Skill {canonical_name: $canonical})
                MERGE (p)-[:USES]->(s)
                """,
                {"pname": proj["name"], "canonical": canonical},
            )

    # Upsert corporate experiences and HAD edges
    for exp in data.get("experiences", []):
        exp_id = exp.get("id") or f"{c['id']}:exp:{exp.get('title')}:{exp.get('company')}"
        query(
            """
            MERGE (e:Experience {id: $id})
            SET e.title = $title, e.company = $company, e.start_date = $start_date,
                e.end_date = $end_date, e.description = $description
            WITH e
            MATCH (c:Candidate {id: $cid})
            MERGE (c)-[:HAD]->(e)
            """,
            {
                "id": str(exp_id),
                "title": exp.get("title") or "",
                "company": exp.get("company") or "",
                "start_date": str(exp.get("start_date") or ""),
                "end_date": str(exp.get("end_date") or ""),
                "description": exp.get("description") or "",
                "cid": c["id"],
            },
        )


def write_job_posting(job: dict, normalizer):
    # Upsert job posting and REQUIRES edges
    query(
        "MERGE (j:JobPosting {id: $id}) SET j.title = $title, j.company = $company, j.url = $url",
        {"id": job.get("id"), "title": job.get("title"), "company": job.get("company"), "url": job.get("url")},
    )

    for req in job.get("requirements", []):
        canonical = normalizer.normalize(req.get("name"))
        importance = req.get("importance", 1.0)
        query(
            """
            MATCH (j:JobPosting {id: $jid})
            MERGE (s:Skill {canonical_name: $canonical})
            MERGE (j)-[r:REQUIRES]->(s)
            SET r.importance = $importance
            """,
            {"jid": job.get("id"), "canonical": canonical, "importance": importance},
        )