import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///career_graph.db")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema_compatibility():
    """Add nullable columns required by newer ORM models to legacy SQLite DBs.

    Some local databases were created with ``Base.metadata.create_all`` before
    candidate profile fields were introduced. SQLite's create_all does not
    alter existing tables, so those databases need this additive repair before
    SQLAlchemy can select Candidate rows.
    """
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in ("candidates", "job_postings")
        if table_name in inspector.get_table_names()
    }

    missing_columns = {
        "candidates": {
            "location": "VARCHAR(255)",
            "experience_level": "VARCHAR(128)",
        },
        "job_postings": {
            "location": "VARCHAR(255)",
            "experience_level": "VARCHAR(128)",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in missing_columns.items():
            if table_name not in table_columns:
                continue
            existing_columns = table_columns.get(table_name, set())
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )


ensure_schema_compatibility()

def init_db(base):
    """Create database tables."""
    base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()

def get_session():
    return SessionLocal()