import jsonschema


EXTRACTION_SCHEMA = {
    "type": "object",
    "required": ["candidate"],
    "properties": {
        "candidate": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "resume_url": {"type": "string"}},
        },
        "skills": {
            "type": "array",
            "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "confidence": {"type": "number"}, "evidence": {"type": "string"}}},
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "url": {"type": "string"}, "commit_count": {"type": "integer"}, "skills_used": {"type": "array"}},
            },
        },
        "experiences": {"type": "array"},
    },
}


def validate_extraction(data: dict) -> tuple[bool, list]:
    try:
        jsonschema.validate(instance=data, schema=EXTRACTION_SCHEMA)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]