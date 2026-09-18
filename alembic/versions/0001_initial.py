"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'candidates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('canonical_name', sa.String(length=255), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('category', sa.String(length=128), nullable=True),
    )

    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=True),
        sa.Column('commit_count', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=128), nullable=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidates.id'), nullable=True),
    )

    op.create_table(
        'experiences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidates.id'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
    )

    op.create_table(
        'job_postings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=128), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
    )

    # association tables
    op.create_table(
        'candidate_skill',
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidates.id'), primary_key=True),
        sa.Column('skill_id', sa.Integer(), sa.ForeignKey('skills.id'), primary_key=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
    )

    op.create_table(
        'project_skill',
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), primary_key=True),
        sa.Column('skill_id', sa.Integer(), sa.ForeignKey('skills.id'), primary_key=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
    )

    op.create_table(
        'job_requirement',
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('job_postings.id'), primary_key=True),
        sa.Column('skill_id', sa.Integer(), sa.ForeignKey('skills.id'), primary_key=True),
        sa.Column('importance', sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_table('job_requirement')
    op.drop_table('project_skill')
    op.drop_table('candidate_skill')
    op.drop_table('job_postings')
    op.drop_table('experiences')
    op.drop_table('projects')
    op.drop_table('skills')
    op.drop_table('candidates')
