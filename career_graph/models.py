from datetime import datetime
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Association tables with edge properties
candidate_skill = Table(
    "candidate_skill",
    Base.metadata,
    Column("candidate_id", ForeignKey("candidates.id"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id"), primary_key=True),
    Column("confidence", Float, default=0.0),
    Column("evidence", JSON, nullable=True),
)

project_skill = Table(
    "project_skill",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id"), primary_key=True),
    Column("evidence", JSON, nullable=True),
)

job_requirement = Table(
    "job_requirement",
    Base.metadata,
    Column("job_id", ForeignKey("job_postings.id"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id"), primary_key=True),
    Column("importance", Float, default=1.0),
)


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("Skill", secondary=candidate_skill, back_populates="candidates")
    projects = relationship("Project", back_populates="candidate")
    experiences = relationship("Experience", back_populates="candidate")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True)
    canonical_name = Column(String(255), unique=True, nullable=False)
    aliases = Column(JSON, default=list)
    category = Column(String(128), nullable=True)

    candidates = relationship("Candidate", secondary=candidate_skill, back_populates="skills")
    projects = relationship("Project", secondary=project_skill, back_populates="skills")
    job_postings = relationship("JobPosting", secondary=job_requirement, back_populates="skills")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(1024), nullable=True)
    commit_count = Column(Integer, default=0)
    source = Column(String(128), nullable=True)

    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    candidate = relationship("Candidate", back_populates="projects")

    skills = relationship("Skill", secondary=project_skill, back_populates="projects")


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="experiences")


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String(128), nullable=True)
    posted_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("Skill", secondary=job_requirement, back_populates="job_postings")